tropocli
========

`tropocli` is a cli to manage cloudformation templates written in troposphere to be managed and deployed directly, without first generating cloudformation json on yaml files.

## Features

* template validation
    - out-of-the-box support for the cloudformation api's `validate` action
    - future support for libraries, such as [`cloudformation-validator`](https://github.com/aws-samples/aws-cloudformation-validator)
* stateless deployment: deploy cloudformation templates using changesets in a single command, with the ability to preview changes to a deployed stack
* better ui: a terminal ui that transparently reports stack status and a ux that allows for simpler management (update/delete/status) of stacks

## Installation

To be determined.

## CLI

```
$ tropocli render [template]
$ tropocli validate [template]
$ tropocli preview [template]
$ tropocli apply [template]
$ tropocli delete [template]
```

## License

This project is MIT licensed.
See `license.txt` for more details.
