"""Neo4j graph and GraphQL server for Mnemon integration.

Uses PEP 562 lazy imports so neo4j/strawberry are only loaded when accessed.
"""

__all__ = ["Neo4jGraph", "GraphQLServer"]


def __getattr__(name: str):
    import importlib

    _submodules = {"neo4j_graph", "graphql_server"}
    if name in _submodules:
        return importlib.import_module(f".{name}", __name__)

    _class_map = {
        "Neo4jGraph": ".neo4j_graph",
        "GraphQLServer": ".graphql_server",
    }
    if name in _class_map:
        mod = importlib.import_module(_class_map[name], __name__)
        return getattr(mod, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
