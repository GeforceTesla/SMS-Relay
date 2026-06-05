from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_keypair(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = output_dir / "server_private.pem"
    public_path = output_dir / "server_public.pem"
    private_path.write_bytes(private_bytes)
    public_path.write_bytes(public_bytes)
    private_path.chmod(0o600)
    public_path.chmod(0o644)

    print(f"Wrote {private_path}")
    print(f"Wrote {public_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SMS relay RSA keypair")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("keys"),
        help="Directory for server_private.pem and server_public.pem",
    )
    args = parser.parse_args()
    generate_keypair(args.output_dir)


if __name__ == "__main__":
    main()
