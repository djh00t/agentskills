When using spec-kit, you need to use the prompts and templates that are bundled
with it.

Generally the repo is initialised with a copy of the spec-kit templates, and
then you run /speckit.constitution to generate the core ruleset and guiding
principles for the project. Sometimes more information is needed from the user,
you should allow for this.

The second step is to run /speckit.specify, feeding it the specification you
want to implement. This will generate a structured specification. The user
should provide feedback if its required, the tool will usually prompt you for
more information OR it will tell you the next prompt to run which is usually
/speckit.tasks which will generate a set of tasks to implement the
specification.

Once the tasks are generated, you should run /speckit.analyze to analyze the
overall outputs so far and to figure out 