- **Flux generation**: This add a new technical report template kind which
  allow to create loops, if statements and other kind of "flux variables".
  All these flux variables defines a line of the flux file. These variables
  will be evaluated as genshi language to create the final output line for each
  selected/given records. It is also possible to override the main loop
  condition to, for instance, aggregate output lines.
