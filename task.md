There are currently two functions for executing hooks: `execute` and `execute_pipeline`.

In actuality, any hook that should be executed using `execute_pipeline` should
always be executed using `execute_pipeline`. Any hook that should be executed
using `execute` should always be executed using `execute`. We should add an attribute
to the Hook class to indicate which execution method should be used. Then, we should
merge the two functions into a single `execute` function that checks the attribute
and proceeds accordingly.
