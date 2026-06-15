"""Vault indexer placeholder — will be replaced by Task 8."""


class VaultIndexer:
    """Placeholder VaultIndexer."""

    def __init__(self, vault_dir: str = "./kgsrc/pkos/vault", indexed_file: str = "./pkos_indexed.json"):
        pass

    def index_document(self, file_path: str) -> bool:
        return True

    def index_all_unindexed(self) -> int:
        return 0

    def get_indexed_documents(self):
        return []

    def mark_indexed(self, file_path: str):
        pass
