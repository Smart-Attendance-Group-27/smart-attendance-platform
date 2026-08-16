# Contribution Guidelines

## Main Branch

The `main` branch is the shared integration branch.

No member should push feature work directly to `main`.

## Branch Naming

Use one of the following patterns:

- `feat/mobile-feature-name`
- `fix/mobile-problem-name`
- `test/mobile-test-name`
- `docs/topic-name`
- `chore/setup-name`
- `refactor/mobile-area-name`

Examples:

- `feat/mobile-login-screen`
- `fix/mobile-location-permission`
- `test/mobile-login-validation`
- `chore/initial-monorepo-setup`

## Development Workflow

1. Update the local `main` branch.
2. Create a new branch from `main`.
3. Implement one focused change.
4. Commit the change using a clear message.
5. Push the branch.
6. Open a pull request targeting `main`.
7. Request one teammate review.
8. Address all review comments.
9. Merge using squash merging.


## Commit Messages

Use the following format:

`type(scope): description`

Examples:

- `feat(mobile): add student login form`
- `fix(mobile): handle denied location permission`
- `test(mobile): add login validation tests`
- `docs(mobile): document check-in workflow`

Avoid commit messages such as:

- `update`
- `done`
- `changes`
- `final`
- `fix`

## Pull Request Requirements

A pull request should:

- Describe the change
- Contain one focused feature or correction
- Include testing information
- Include screenshots for interface changes
- Pass linting and automated tests
- Receive at least one teammate approval