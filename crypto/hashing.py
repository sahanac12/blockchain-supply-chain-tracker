import hashlib
import json

def hash_bytes(data: bytes) -> str:
    """
    Returns the SHA-256 hash of raw bytes as a hex string.
    """
    return hashlib.sha256(data).hexdigest()

def hash_string(data: str) -> str:
    """
    Returns the SHA-256 hash of a string as a hex string.
    """
    return hash_bytes(data.encode('utf-8'))

def hash_dict(data: dict) -> str:
    """
    Returns the SHA-256 hash of a dictionary as a hex string, 
    serializing it with sorted keys to ensure determinism.
    """
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hash_string(serialized)

class MerkleTree:
    def __init__(self, leaves: list[str]):
        """
        Builds a Merkle Tree from a list of leaf hashes (hex strings).
        If leaves is empty, initializes with a single dummy leaf of zeros.
        """
        self.leaves = leaves if leaves else [hash_string("")]
        self.tree_levels = []
        self.build_tree()

    def build_tree(self):
        """
        Constructs the tree bottom-up.
        """
        current_level = self.leaves
        self.tree_levels.append(current_level)

        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                # If there is no right sibling, duplicate the left sibling
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                
                # Combine and hash
                combined = left + right
                parent_hash = hash_string(combined)
                next_level.append(parent_hash)
            
            current_level = next_level
            self.tree_levels.append(current_level)

    def get_root(self) -> str:
        """
        Returns the root hash of the Merkle Tree.
        """
        return self.tree_levels[-1][0]

    def get_proof(self, index: int) -> list[dict]:
        """
        Generates a Merkle Proof for the leaf at the specified index.
        A proof is a list of sibling hashes and their directions ('left' or 'right').
        """
        if index < 0 or index >= len(self.leaves):
            raise IndexError("Leaf index out of bounds")

        proof = []
        current_index = index

        # Traverse up the tree levels, excluding the root level
        for level in self.tree_levels[:-1]:
            # Determine if current node is a left or right child
            is_right_child = (current_index % 2 == 1)
            
            if is_right_child:
                # Sibling is to the left
                sibling_index = current_index - 1
                direction = "left"
            else:
                # Sibling is to the right (or self if odd elements at the end)
                sibling_index = current_index + 1
                direction = "right"
                if sibling_index >= len(level):
                    sibling_index = current_index  # duplicate last leaf node behavior

            proof.append({
                "hash": level[sibling_index],
                "direction": direction
            })
            
            current_index = current_index // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: list[dict], root_hash: str) -> bool:
        """
        Verifies that a leaf hash is part of a Merkle Tree with the given root hash using a Merkle Proof.
        """
        current_hash = leaf_hash
        for step in proof:
            sibling_hash = step["hash"]
            direction = step["direction"]

            if direction == "left":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash
            
            current_hash = hash_string(combined)

        return current_hash == root_hash
