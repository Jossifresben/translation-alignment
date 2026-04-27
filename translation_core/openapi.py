"""OpenAPI 3.0 spec for the Polyglot Concordance API v1.

Hand-written (no auto-generation framework) since the API surface is small
and the schemas are domain-specific. Served at /api/v1/openapi.json and
rendered by Swagger UI at /api/docs.
"""

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Polyglot Concordance API",
        "description": (
            "Read-only JSON access to the alignment data and search index of the "
            "Polyglot Concordance — a concordance initiative with alignment to the "
            "word level, covering the Gospel of Mark across the Greek NT, Syriac "
            "Peshitta, and Latin Clementine Vulgate, with a critical apparatus on "
            "every divergence."
        ),
        "version": "1.0.0",
        "contact": {
            "name": "Jossi Fresco Benaim",
            "email": "jossi@somosunodigital.com",
            "url": "https://orcid.org/0009-0000-2026-0836",
        },
        "license": {
            "name": "CC BY 4.0 (derived data) + open-source (code, intended)",
        },
    },
    "servers": [
        {"url": "https://polyglotconcordance.com", "description": "Production"},
    ],
    "tags": [
        {"name": "alignment", "description": "Per-verse alignment artifacts"},
        {"name": "search", "description": "Verse-level full-text search"},
        {"name": "meta", "description": "Corpus metadata + API metadata"},
    ],
    "paths": {
        "/api/v1/alignment/{book}/{chapter}/{verse}": {
            "get": {
                "tags": ["alignment"],
                "summary": "Canonical alignment JSON for one verse",
                "description": (
                    "Returns the on-disk alignment artifact for the verse, with "
                    "tokens per tradition, alignment groups (verdict, type, "
                    "confidence, apparatus note), and metadata."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/BookParam"},
                    {"$ref": "#/components/parameters/ChapterParam"},
                    {"$ref": "#/components/parameters/VerseParam"},
                ],
                "responses": {
                    "200": {
                        "description": "Alignment found",
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/Alignment"}
                        }},
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            }
        },
        "/api/v1/verse/{book}/{chapter}/{verse}": {
            "get": {
                "tags": ["alignment"],
                "summary": "Display-shape verse dict (witnesses + variants + gloss_map)",
                "description": (
                    "Returns the same shape consumed by the rendered HTML viewer: "
                    "witnesses array (each with tokens carrying align-IDs and "
                    "variant tags), variants array, and `gloss_map` with verse "
                    "translations for all four supported languages."
                ),
                "parameters": [
                    {"$ref": "#/components/parameters/BookParam"},
                    {"$ref": "#/components/parameters/ChapterParam"},
                    {"$ref": "#/components/parameters/VerseParam"},
                ],
                "responses": {
                    "200": {
                        "description": "Verse found",
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/Verse"}
                        }},
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            }
        },
        "/api/v1/search": {
            "get": {
                "tags": ["search"],
                "summary": "Verse-level search across all witnesses",
                "description": (
                    "Searches Greek, Latin, Syriac, English (WEB), and variant "
                    "types. The query `13:14` (chapter:verse) is treated as a "
                    "reference jump and returns that single verse."
                ),
                "parameters": [
                    {"name": "q", "in": "query", "required": False,
                     "schema": {"type": "string"},
                     "description": "Search string, or `chapter:verse` reference jump"},
                    {"name": "limit", "in": "query", "required": False,
                     "schema": {"type": "integer", "default": 25, "minimum": 1, "maximum": 100},
                     "description": "Max results to return (clamped to [1, 100])"},
                ],
                "responses": {
                    "200": {
                        "description": "Search results (possibly empty)",
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/SearchResults"}
                        }},
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                },
            }
        },
        "/api/v1/manifest": {
            "get": {
                "tags": ["meta"],
                "summary": "Corpus + API metadata",
                "description": (
                    "Returns the project description, schema version, "
                    "the list of books in scope (with full verse enumeration), "
                    "the witnesses, the four supported gloss editions, the "
                    "controlled vocabularies for variant verdicts/types, and "
                    "the alignment generation provenance."
                ),
                "responses": {
                    "200": {
                        "description": "Manifest",
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/Manifest"}
                        }},
                    },
                },
            }
        },
        "/api/v1/openapi.json": {
            "get": {
                "tags": ["meta"],
                "summary": "This OpenAPI spec",
                "responses": {
                    "200": {
                        "description": "OpenAPI 3.0 spec document",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                },
            }
        },
    },
    "components": {
        "parameters": {
            "BookParam": {
                "name": "book", "in": "path", "required": True,
                "schema": {"type": "string", "enum": ["mark"]},
                "description": "Book id (currently only `mark`)",
            },
            "ChapterParam": {
                "name": "chapter", "in": "path", "required": True,
                "schema": {"type": "integer", "minimum": 1, "maximum": 16},
            },
            "VerseParam": {
                "name": "verse", "in": "path", "required": True,
                "schema": {"type": "integer", "minimum": 1},
            },
        },
        "responses": {
            "NotFound": {
                "description": "Resource not found",
                "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"}
                }},
            },
            "BadRequest": {
                "description": "Malformed query parameters",
                "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/Error"}
                }},
            },
        },
        "schemas": {
            "Error": {
                "type": "object",
                "required": ["error"],
                "properties": {
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "example": "verse_not_found"},
                            "message": {"type": "string"},
                        },
                    },
                },
            },
            "Alignment": {
                "type": "object",
                "properties": {
                    "api_version": {"type": "string", "example": "v1"},
                    "ref":     {"type": "string", "example": "Mark 13:14"},
                    "chapter": {"type": "integer"},
                    "verse":   {"type": "integer"},
                    "traditions": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "tokens": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "alignment": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/AlignmentGroup"},
                    },
                    "meta": {"type": "object"},
                },
            },
            "AlignmentGroup": {
                "type": "object",
                "properties": {
                    "id":         {"type": "string"},
                    "members":    {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array", "items": {"type": "integer"}
                        },
                    },
                    "verdict":    {"type": "string",
                                   "enum": ["aligned", "minor", "major", "omitted", "added"]},
                    "type":       {"type": "string"},
                    "note":       {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
            "Verse": {
                "type": "object",
                "properties": {
                    "api_version": {"type": "string", "example": "v1"},
                    "ref":     {"type": "string"},
                    "book":    {"type": "string"},
                    "chapter": {"type": "integer"},
                    "verse":   {"type": "integer"},
                    "pericope":  {"type": "string"},
                    "testament": {"type": "string"},
                    "witnesses": {"type": "array", "items": {"type": "object"}},
                    "variants":  {"type": "array", "items": {"type": "object"}},
                    "gloss_map": {
                        "type": "object",
                        "properties": {
                            "en":      {"type": "string"},
                            "es":      {"type": "string"},
                            "zh-Hans": {"type": "string"},
                            "zh-Hant": {"type": "string"},
                        },
                    },
                    "prev": {"type": "object", "nullable": True},
                    "next": {"type": "object", "nullable": True},
                },
            },
            "SearchResults": {
                "type": "object",
                "properties": {
                    "api_version": {"type": "string", "example": "v1"},
                    "query": {"type": "string"},
                    "count": {"type": "integer"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ref":         {"type": "string"},
                                "chapter":     {"type": "integer"},
                                "verse":       {"type": "integer"},
                                "snippet":     {"type": "string"},
                                "kind":        {"type": "string"},
                                "matched_in":  {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
            "Manifest": {
                "type": "object",
                "properties": {
                    "api_version": {"type": "string", "example": "v1"},
                    "project":     {"type": "string"},
                    "description": {"type": "string"},
                    "license":     {"type": "string"},
                    "schema_version": {"type": "integer"},
                    "books":          {"type": "array", "items": {"type": "object"}},
                    "witnesses":      {"type": "array", "items": {"type": "object"}},
                    "verse_glosses":  {"type": "array", "items": {"type": "object"}},
                    "variant_verdicts": {"type": "array", "items": {"type": "string"}},
                    "variant_types":    {"type": "array", "items": {"type": "string"}},
                    "alignment_generation": {"type": "object"},
                    "endpoints":      {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}
