- **Rule engine :** Allows creating rules using a simplified macro language.
  When executing the rule, used symbols are replaced by corresponding business
  data.

- **Recursive rules :** It is possible to call a rule from another rule.
  This allows maximum mutualisation of the setting between different business
  lines, or different options.

- **Tables use :** Tables are a concise way of creating settings. From a rule,
  it is possible to look for a table's result using arbitrary parameters, and
  to manipulate / use the resulting value in the rule's algorithm.

- **Rule parameters :** Some rules are often used. Typically, the eligibility
  rule is based on the insured person's age in health and life claims. It is
  possible to define a parameter for the rule (for example: maximum allowed
  age), which will be asked for each time the rule is parametered on a coverage.


- ** Test cases :** Complex algorithms are difficult to update. Making an
  attention mistake is possible. Therefore, it is possible to create test cases
  on a rule. They allow to store an entry configuration, and the expected
  result. After a change, test cases are executed to make sure results are the
  ones expected.

- **Debug mode :** Debug mode allows to picture different steps of the rule's
  execution, with all its associated parameters. It is possible to generate
  test cases from these steps. It allows to:

  - Execute real cases

  - Understand why the obtained result does not match the expected one

  - Correct and retest

  - Once the result is correct, generate test cases

- **Pre-parametered rules :** Most used rules can be provided by default
  in *Coog*
