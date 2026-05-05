"""
gdtest_nested_class — Inner/nested classes.

Dimensions: A1, B1, C11, D1, E6, F6, G1, H7
Focus: 1 outer class containing 1 inner class.
       Tests nested class discovery and documentation.
"""

SPEC = {
    "name": "gdtest_nested_class",
    "description": "Nested/inner class handling",
    "dimensions": ["A1", "B1", "C11", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-nested-class",
            "version": "0.1.0",
            "description": "A synthetic test package with nested classes",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_nested_class/__init__.py": '''\
            """A test package with nested classes."""

            __version__ = "0.1.0"
            __all__ = ["Tree"]


            class Tree:
                """
                A tree data structure with a nested Node class.

                Parameters
                ----------
                root_value
                    Value for the root node.
                """

                class Node:
                    """
                    A tree node.

                    Parameters
                    ----------
                    value
                        The node value.
                    """

                    def __init__(self, value):
                        self.value = value
                        self.children = []

                    def add_child(self, value) -> "Tree.Node":
                        """
                        Add a child node.

                        Parameters
                        ----------
                        value
                            The child's value.

                        Returns
                        -------
                        Tree.Node
                            The new child node.
                        """
                        child = Tree.Node(value)
                        self.children.append(child)
                        return child

                    def is_leaf(self) -> bool:
                        """
                        Check if this node is a leaf.

                        Returns
                        -------
                        bool
                            True if no children.
                        """
                        return len(self.children) == 0

                def __init__(self, root_value=None):
                    self.root = self.Node(root_value) if root_value is not None else None

                def depth(self) -> int:
                    """
                    Calculate the depth of the tree.

                    Returns
                    -------
                    int
                        Maximum depth from root to leaf.
                    """
                    if self.root is None:
                        return 0

                    def _depth(node):
                        if not node.children:
                            return 1
                        return 1 + max(_depth(c) for c in node.children)

                    return _depth(self.root)

                def size(self) -> int:
                    """
                    Count the total number of nodes.

                    Returns
                    -------
                    int
                        Total number of nodes.
                    """
                    if self.root is None:
                        return 0

                    def _count(node):
                        return 1 + sum(_count(c) for c in node.children)

                    return _count(self.root)
        ''',
        "README.md": """\
            # gdtest-nested-class

            A synthetic test package with nested classes.
        """,
    },
    "expected": {
        "detected_name": "gdtest-nested-class",
        "detected_module": "gdtest_nested_class",
        "detected_parser": "numpy",
        "export_names": ["Tree"],
        "num_exports": 1,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
