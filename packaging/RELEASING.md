# Releasing

Releases are built and published manually by the **Release (Windows EXE)**
GitHub Actions workflow (`.github/workflows/release.yml`). It builds a single
self-contained `RT98Studio.exe` (app + Python deps + qgif WASM + Node + ffmpeg),
GPG-signs it, and publishes a GitHub Release with your title and notes.

## One-time setup: repository secrets

Add these under **Settings -> Secrets and variables -> Actions**:

| Secret | What it is |
|--------|------------|
| `GPG_PRIVATE_KEY` | The ASCII-armored GPG **private** key used to sign the exe. |
| `GPG_PASSPHRASE`  | That key's passphrase (leave empty if the key has none). |

Generate and export a signing key (locally):

```sh
gpg --full-generate-key                      # choose RSA 4096 (or ed25519)
gpg --list-secret-keys --keyid-format=long   # note the key id
gpg --armor --export-secret-keys <KEYID>     # paste this into GPG_PRIVATE_KEY
gpg --armor --export <KEYID> > RT98Studio-signing-key.asc   # public key, for reference
```

`GITHUB_TOKEN` is provided automatically; the workflow has `contents: write`.

## Cutting a release

1. Push the commit you want to release.
2. GitHub -> **Actions** -> **Release (Windows EXE)** -> **Run workflow**.
3. Fill in:
   - **tag** - e.g. `v0.1.0` (created at the commit you ran from)
   - **title** - the release title
   - **notes** - Markdown description (optional)
   - **prerelease** - check for a pre-release
4. The release appears with `RT98Studio.exe` plus its signature, checksum, and
   the public key.

## How users verify the download

```sh
gpg --import RT98Studio-signing-key.asc
gpg --verify RT98Studio.exe.asc RT98Studio.exe          # expect "Good signature"
sha256sum -c RT98Studio.exe.sha256                       # integrity check
```

## Notes

- The exe is GPG-signed, **not** Windows Authenticode-signed. Windows SmartScreen
  may still warn on first run; that requires a separate code-signing certificate.
- The bundled Node + ffmpeg make the exe fully self-contained (no installs), at
  the cost of size (~100-150 MB). Bump the Node version in the workflow's
  "Fetch bundled runtimes" step as needed.
- The git tag itself is not GPG-signed (only the artifact). Sign the tag
  separately if you want a "Verified" badge on the tag.
