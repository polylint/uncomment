# @polylint/uncomment-linux-arm64-gnu

The prebuilt `uncomment` binary for **Linux arm64 (glibc)** (`aarch64-unknown-linux-gnu`).

This package exists only so that [`@polylint/uncomment`](https://www.npmjs.com/package/@polylint/uncomment)
can pull exactly one platform binary through `optionalDependencies`. Install that
package instead; it is what puts the `uncomment` command on your `PATH`:

```sh
npm i -g @polylint/uncomment
```
