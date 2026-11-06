# Release automation

The `Build and publish release` workflow builds all supported distributions from a version tag:

- Windows x64 portable executable and installer wizard.
- macOS Apple silicon DMG.
- macOS Intel DMG.
- SHA-256 checksum file beside every downloadable release asset.

It runs automatically when a tag matching `v*` is pushed. For example:

```bash
git tag v2.1.0
git push origin v2.1.0
```

The workflow can also be started manually from **Actions > Build and publish release**. Manual runs create downloadable workflow artifacts but do not publish a GitHub Release.

## Unsigned release builds

No configuration is required to produce functional artifacts. Without signing secrets, the workflow still publishes the Windows executable, Windows installer, and both macOS DMGs. macOS builds use PyInstaller's required ad-hoc signatures, so Gatekeeper will identify them as unverified. Windows may show a SmartScreen warning for unsigned files.

## Production signing and notarization

For public distribution, configure the following repository secrets under **Settings > Secrets and variables > Actions**. Never commit certificates, passwords, or Apple API keys to the repository.

| Secret | Purpose | Required for |
| --- | --- | --- |
| `WINDOWS_CERTIFICATE_BASE64` | Base64-encoded code-signing PFX certificate | Signing Windows files |
| `WINDOWS_CERTIFICATE_PASSWORD` | Password for the Windows PFX certificate | Signing Windows files |
| `APPLE_CERTIFICATE_BASE64` | Base64-encoded Developer ID Application `.p12` certificate | Signing the macOS app bundle |
| `APPLE_CERTIFICATE_PASSWORD` | Password for the Apple `.p12` certificate | Signing the macOS app bundle |
| `APPLE_CODESIGN_IDENTITY` | Exact certificate identity, for example `Developer ID Application: Company Name (TEAMID)` | Signing the macOS app bundle |
| `APPLE_KEYCHAIN_PASSWORD` | Random temporary keychain password | Recommended for macOS signing |
| `APPLE_NOTARY_KEY_BASE64` | Base64-encoded App Store Connect API private key (`.p8`) | Notarizing macOS DMG |
| `APPLE_NOTARY_KEY_ID` | App Store Connect API key identifier | Notarizing macOS DMG |
| `APPLE_NOTARY_ISSUER_ID` | App Store Connect issuer UUID | Notarizing macOS DMG |

Encode the certificate and API-key files on macOS before adding them as secrets:

```bash
base64 -i developer-id-application.p12 -o developer-id-application.base64
base64 -i AuthKey_ABC123DEFG.p8 -o AuthKey_ABC123DEFG.base64
```

The workflow imports the certificate into a temporary runner keychain, verifies the signature, submits the completed DMG to Apple's notary service, waits for its result, and staples the resulting ticket. The temporary GitHub-hosted runner is discarded after the job.

Apple requires a valid Developer ID certificate and hardened runtime for direct-distribution notarization. Windows signing requires a certificate trusted by Windows clients. Both certificates should be acquired from a reputable certificate authority or their respective platform vendor.

## Artifact verification

Every release contains a matching `.sha256` file. Verify a downloaded file before distributing or installing it.

On macOS or Linux:

```bash
shasum -a 256 -c WhatsAppCapitalize-2.1.0-macos-arm64.dmg.sha256
```

On Windows PowerShell:

```powershell
Get-FileHash .\WhatsAppCapitalize-Setup-2.1.0-win64.exe -Algorithm SHA256
```

Compare the printed hash with the accompanying `.sha256` file.
