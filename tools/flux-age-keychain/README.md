# flux-age-keychain

A small signed macOS helper that saves secrets to **iCloud Keychain** (the data protection keychain, `kSecAttrSynchronizable = true`), so they sync to your other Macs.

The `security` CLI can't do this. It only writes the local login keychain, which never syncs ([TN3137](https://developer.apple.com/documentation/technotes/tn3137-on-mac-keychains)). An unsigned or ad-hoc binary gets `-34018` (missing entitlement), and an ad-hoc binary that claims `keychain-access-groups` is killed at launch. So the helper ships as an `.app` bundle with an embedded **Developer ID provisioning profile**.

This directory is the canonical source.

## Caveats

- **Only this signed helper can read the items.** They live in the team-scoped access group `<TeamID>.<suffix>`, where the suffix comes from `FLUX_AGE_GROUP_SUFFIX` (default `com.example.flux-age`). Every build that must read the same items needs the same team and suffix. The `security` CLI and the Passwords app can't read them, and Passwords doesn't list them. Keychain Access shows them under **iCloud**.
- **To read them on another Mac**, turn on iCloud Keychain there (System Settings → your name → iCloud → Passwords & Keychain), install the same `FluxAgeKeychain.app` signed by the same team, then run `flux-age-keychain get <service>`.
- **A delete syncs everywhere.** The helper has no delete command, and `set` never overwrites. Never tidy `flux-age/*` items in Keychain Access.
- Service names must be `flux-age/<name>` or `flux-age/<name>/previous`, where `<name>` matches `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`. Secrets must be one line. One trailing LF or CRLF is dropped; any other CR, LF or NUL is refused.

## Commands

| Command | What it does | Exit codes |
|---|---|---|
| `set <service>` | Reads the secret from stdin, adds it, then reads it back to check. Never overwrites. | 0, 2 bad input, 3 exists, 6 keychain error |
| `get <service>` | Writes the secret to stdout. Use it only in a pipe. | 0, 4 missing, 6 keychain error |
| `exists <service>` | Prints nothing. | 0 present, 4 missing, 6 keychain error |
| `list` | Prints service names only. | 0, 6 keychain error |
| `replace <service> --previous <service>/previous` | Saves the current value as `/previous`, then writes the new one from stdin. | 0, 2 bad input, 4 missing, 5 unchanged, 6 keychain error |
| `doctor` | Checks the team ID, access group and keychain. | 0 ok, 6 not usable |

Every command also exits 2 on a usage error (unknown command, bad service name or bad arguments).

The helper reads secrets only from stdin, never from arguments or the environment, and refuses to read one from a terminal.

Copy a login-keychain item into iCloud Keychain and check it, without printing the value:

```shell
set +x
security find-generic-password -s SRC -a ACCOUNT -w | flux-age-keychain set flux-age/NAME
[ "$(security find-generic-password -s SRC -a ACCOUNT -w | shasum -a 256)" = \
  "$(flux-age-keychain get flux-age/NAME | shasum -a 256)" ] && echo match
```

## Build and install (macOS)

One-time Apple setup (Account Holder): create a Developer ID Application certificate, an explicit App ID (for example `com.example.flux-age-keychain`), and a macOS **Developer ID** provisioning profile for that App ID that allows the keychain access group `<TeamID>.<suffix>`. Replace `com.example` with your own reverse-DNS prefix by setting `FLUX_AGE_BUNDLE_ID` and `FLUX_AGE_GROUP_SUFFIX`. Save the profile outside the repo at `~/.config/flux-age-keychain/FluxAgeKeychain.provisionprofile` (mode 600). Optionally, add `~/.config/flux-age-keychain/package.env` containing `FLUX_AGE_TEAM_ID`, `FLUX_AGE_BUNDLE_ID` and `FLUX_AGE_GROUP_SUFFIX` as plain `KEY=value` lines. `package.sh` sources that file as shell, so its values take precedence over the environment. A signed build refuses the `com.example.*` placeholders; they are accepted only with `./package.sh --unsigned`.

```shell
make check            # swift test plus a source check that no delete API is called
make build            # debug build (swift build)
make quality-gates    # make check plus shellcheck package.sh (when shellcheck is installed)
make install          # ./package.sh (signed), then install the app in ~/Applications
                      # and link the binary into ~/.local/bin
flux-age-keychain doctor   # must print "status: ok"
```

Never commit certificates, profiles, `.p12` files, Team IDs or secrets. `.gitignore` excludes them.
