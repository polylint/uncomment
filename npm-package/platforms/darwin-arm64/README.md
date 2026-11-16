# @polylint/uncomment-darwin-arm64

The prebuilt `uncomment` binary for **macOS (Apple silicon)** (`aarch64-apple-darwin`).

This package exists only so that [`@polylint/uncomment`](https://www.npmjs.com/package/@polylint/uncomment)
can pull exactly one platform binary through `optionalDependencies`. Install that
package instead; it is what puts the `uncomment` command on your `PATH`:

```sh
npm i -g @polylint/uncomment
```
