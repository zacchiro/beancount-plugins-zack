Zack's plugins for Beancount
============================

Various plugins for the [Beancount](http://furius.ca/beancount/) accounting
tool.

The following plugins are currently available:

- **file_ordering**: enforces strict date ordering within individual Beancount
  files
- **no_missing_documents**: makes sure that documents referenced from Beancount
  exist as files on disk
- **validate**: rule-based data validation for Beancount ledgers using a simple
  Python-based DSL
- **cerberus_validate**: rule-based data validation for Beancount ledgers
  using, via [Cerberus](http://docs.python-cerberus.org)


License
-------

Copyright (C) Stefano Zacchiroli <zack@upsilon.cc>

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

See the top-level `LICENSE` file for the full-text of the GNU General Public
License, version 2.
