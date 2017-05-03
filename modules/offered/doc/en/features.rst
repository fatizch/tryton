- **Coverage Management**: Configure coverages that can be used when creing
  products. Coverages are service descriptions which will be part of the
  contract that subscribe them. They can be typed, and customized using extra
  data

- **Product Management**: Products are coverages groups that make the basis of
  every service contract. They allow to assemble coverages in a coherent
  structure, and allows subscribers to have one contract for similar services
  rather than several contracts

- **Package Management**: In order to hide the coverages complexity inside a
  product, packages offers an extra abstraction layer to the subscriber by
  grouping multiple coverages together. Those packages are then available in
  the products configuration, for use in contract subscriptions

- **Coverage dependency / exclusions**: Coverages can be defined as exclusive
  or dependant. So a coverage may require another one to be subscribed, or two
  coverages can be made incompatible, so both cannot be subscribed togeter

- **Extra data**: Products and coverages can be linked to extra data. This
  allows advanced contract customization by asking specific questions on each
  contract depending on the subscribed product. Extra data have several types
  (dates, numerics, strings...) and can be made dependant on one another. So it
  is possible to configure that if an extra data has a specific value, another
  one must be set

- **Automatic coverage termination**: When describing a coverage, it is
  possible to configure a rule that will calculate when the option should be
  terminated
