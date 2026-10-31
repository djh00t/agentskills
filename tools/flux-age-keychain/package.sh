#!/bin/sh
# Build, wrap, sign and verify FluxAgeKeychain.app (spec 1140, WP-35b, #1157).
#
# A command-line tool cannot embed a provisioning profile, and the data protection
# keychain needs a profile-authorized keychain-access-groups entitlement, so the tool
# ships inside a minimal app-like bundle:
#
#   FluxAgeKeychain.app/Contents/{Info.plist, MacOS/flux-age-keychain,
#                                 embedded.provisionprofile, _CodeSignature/}
#
# Usage: package.sh            build, embed the profile, sign with Developer ID, verify
#        package.sh --unsigned build and assemble the bundle only (no profile, no
#                              signing); the result cannot use the keychain
#
# Settings (environment, or KEY=value lines in ~/.config/flux-age-keychain/package.env):
#   FLUX_AGE_TEAM_ID        10-character Apple Developer Team ID (required to sign)
#   FLUX_AGE_BUNDLE_ID      bundle id of the App ID (default au.titanicar.flux-age-keychain)
#   FLUX_AGE_PROFILE        Developer ID provisioning profile
#                           (default ~/.config/flux-age-keychain/FluxAgeKeychain.provisionprofile)
#   FLUX_AGE_SIGN_IDENTITY  codesign identity (default "Developer ID Application")
#   FLUX_AGE_OUT            output directory (default <package>/dist)
#
# The keychain access group is fixed at <team id>.au.titanicar.flux-age (#1157). It names
# the stored flux-age/* data, not this binary, and is deliberately not configurable: a
# build signed with any other group cannot see the existing keys.
#
# It never reads or writes a keychain item and never prints a secret. Notarization is a
# separate, optional step described in docs/runbooks/flux-age-keychain.md.

set -eu
set +x

die() {
    printf 'package: %s\n' "$*" >&2
    exit 2
}

[ "$(uname -s)" = Darwin ] || die "macOS only (needs swift, codesign and the Security framework)"

unsigned=0
case ${1:-} in
    "") ;;
    --unsigned) unsigned=1 ;;
    *) die "usage: package.sh [--unsigned]" ;;
esac

config_dir="$HOME/.config/flux-age-keychain"
if [ -f "$config_dir/package.env" ]; then
    # shellcheck disable=SC1091 # David's own settings file, outside the repo
    . "$config_dir/package.env"
fi

pkg=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
bundle_id=${FLUX_AGE_BUNDLE_ID:-au.titanicar.flux-age-keychain}
profile=${FLUX_AGE_PROFILE:-$config_dir/FluxAgeKeychain.provisionprofile}
identity=${FLUX_AGE_SIGN_IDENTITY:-Developer ID Application}
out=${FLUX_AGE_OUT:-$pkg/dist}
app="$out/FluxAgeKeychain.app"

printf '%s\n' "$bundle_id" | grep -Eq '^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$' \
    || die "FLUX_AGE_BUNDLE_ID is not a reverse-DNS bundle id: $bundle_id"

if [ "$unsigned" -eq 0 ]; then
    team=${FLUX_AGE_TEAM_ID:-}
    [ -n "$team" ] || die "FLUX_AGE_TEAM_ID is not set"
    printf '%s\n' "$team" | grep -Eq '^[A-Z0-9]{10}$' || die "FLUX_AGE_TEAM_ID must be 10 characters A-Z0-9"
    group=$team.au.titanicar.flux-age
    [ -f "$profile" ] || die "provisioning profile not found: $profile"
fi

work=$(mktemp -d "${TMPDIR:-/tmp}/flux-age-package.XXXXXX")
trap 'rm -rf "$work"' EXIT

# 1. Build.
swift build --package-path "$pkg" -c release --product flux-age-keychain >&2
bin=$(swift build --package-path "$pkg" -c release --show-bin-path)/flux-age-keychain
[ -x "$bin" ] || die "build did not produce $bin"

# 2. Assemble the bundle.
rm -rf "$app"
mkdir -p "$app/Contents/MacOS"
cp "$bin" "$app/Contents/MacOS/flux-age-keychain"
version=$("$bin" --version | awk '{print $2}')
cat >"$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleExecutable</key>
	<string>flux-age-keychain</string>
	<key>CFBundleIdentifier</key>
	<string>$bundle_id</string>
	<key>CFBundleName</key>
	<string>FluxAgeKeychain</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>$version</string>
	<key>CFBundleVersion</key>
	<string>$version</string>
	<key>LSMinimumSystemVersion</key>
	<string>13.0</string>
	<key>LSUIElement</key>
	<true/>
</dict>
</plist>
PLIST
plutil -lint "$app/Contents/Info.plist" >/dev/null || die "Info.plist is invalid"

if [ "$unsigned" -eq 1 ]; then
    printf 'unsigned bundle: %s (cannot use the keychain until signed)\n' "$app"
    exit 0
fi

# 3. Check the profile authorizes this team, App ID and access group.
security cms -D -i "$profile" >"$work/profile.plist" 2>/dev/null || die "cannot decode $profile"
pb() { /usr/libexec/PlistBuddy -c "Print $1" "$work/profile.plist" 2>/dev/null; }
pb ':TeamIdentifier:0' | grep -qx "$team" || die "profile is not for team $team"
profile_app=$(pb ':Entitlements:com.apple.application-identifier') || die "profile has no application-identifier"
# shellcheck disable=SC2254 # a profile App ID may be a wildcard such as TEAMID.*
case "$team.$bundle_id" in
    $profile_app) ;;
    *) die "profile App ID $profile_app does not match $team.$bundle_id" ;;
esac
pb ':ProvisionsAllDevices' | grep -qx true \
    || die "profile is not a Developer ID profile (it has a device list)"
groups=$(pb ':Entitlements:keychain-access-groups') || die "profile does not allow keychain-access-groups"
allowed=0
for g in $(printf '%s\n' "$groups" | sed -n 's/^ *\([^ {}]*\) *$/\1/p'); do
    # shellcheck disable=SC2254 # profile entries are glob patterns such as TEAMID.*
    case $group in $g) allowed=1 ;; esac
done
[ "$allowed" -eq 1 ] || die "profile keychain-access-groups do not allow $group"

# 4. Render entitlements, embed the profile, sign (no --deep), verify.
sed -e "s/@TEAM_ID@/$team/g" -e "s/@BUNDLE_ID@/$bundle_id/g" -e "s/@ACCESS_GROUP@/$group/g" \
    "$pkg/FluxAgeKeychain.entitlements.template" >"$work/FluxAgeKeychain.entitlements"
plutil -lint "$work/FluxAgeKeychain.entitlements" >/dev/null || die "rendered entitlements are invalid"
cp "$profile" "$app/Contents/embedded.provisionprofile"
codesign --force --options runtime --timestamp \
    --entitlements "$work/FluxAgeKeychain.entitlements" \
    --sign "$identity" "$app"
codesign --verify --strict --verbose=2 "$app"
codesign -d --entitlements - --xml "$app" 2>/dev/null >"$work/signed.plist"
/usr/libexec/PlistBuddy -c 'Print :keychain-access-groups:0' "$work/signed.plist" | grep -qx "$group" \
    || die "signed entitlements do not carry $group"
codesign -dv "$app" 2>&1 | grep -q 'flags=.*runtime' || die "hardened runtime is not on"
printf 'signed bundle: %s\naccess group: %s\n' "$app" "$group"
