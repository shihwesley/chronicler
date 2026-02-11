from pydantic import BaseModel, Field
from typing import Literal


class LLMSettings(BaseModel):
    provider: Literal["anthropic", "openai", "google", "ollama", "auto"] = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_tokens: int = Field(default=4096, gt=0)
    timeout: int = Field(default=60, gt=0)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, gt=0)
    base_url: str | None = None


class QueueConfig(BaseModel):
    provider: Literal["sqs", "pubsub", "servicebus", "local"] = "local"
    url: str | None = None
    dlq_url: str | None = None
    max_workers: int = Field(default=5, gt=0)
    visibility_timeout: int = Field(default=300, gt=0)


class VCSConfig(BaseModel):
    provider: Literal["github", "azure", "gitlab"] = "github"
    token_env: str = "GITHUB_TOKEN"
    allowed_orgs: list[str] = Field(default_factory=list)
    rate_limit_buffer: int = 100


class OutputConfig(BaseModel):
    base_dir: str = ".chronicler"
    create_index: bool = True
    validation: Literal["strict", "warn", "off"] = "strict"


class MonorepoConfig(BaseModel):
    detection: Literal["auto", "manifest-only", "convention-only", "disabled"] = "auto"
    package_dirs: list[str] = ["packages", "apps", "services", "libs", "modules"]


class FormatConfig(BaseModel):
    pdf: bool = True
    docx: bool = True
    pptx: bool = True
    xlsx: bool = False
    images: bool = True


class OCRConfig(BaseModel):
    enabled: bool = True
    use_llm: bool = False


class DocCacheConfig(BaseModel):
    enabled: bool = True
    directory: str = ".chronicler/doc_cache"
    ttl_days: int = 7


class DocumentConversionConfig(BaseModel):
    enabled: bool = True
    formats: FormatConfig = Field(default_factory=FormatConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    max_file_size_mb: int = Field(default=50, gt=0)
    max_pages: int = 100
    cache: DocCacheConfig = Field(default_factory=DocCacheConfig)


class PluginsConfig(BaseModel):
    queue: str | None = None
    graph: str | None = None
    rbac: str | None = None
    storage: str | None = None


class MerkleConfig(BaseModel):
    algorithm: str = "sha256"
    doc_dir: str = ".chronicler"
    ignore_patterns: list[str] = Field(default_factory=lambda: [
        ".git", "node_modules", "__pycache__", ".venv", "build", "dist", ".tox", ".worktrees"
    ])
    mercator_path: str | None = None


class ObsidianRestConfig(BaseModel):
    url: str = "https://127.0.0.1:27124"
    token_env: str = "OBSIDIAN_REST_TOKEN"


class ObsidianTransformConfig(BaseModel):
    rewrite_agent_uris: bool = True
    flatten_governance: bool = True
    add_dataview_fields: bool = True
    generate_index: bool = True
    css_class: str = "chronicler-doc"


class ObsidianMappingConfig(BaseModel):
    tags_from: list[str] = Field(default_factory=lambda: ["layer", "security_level", "owner_team"])
    aliases_from: list[str] = Field(default_factory=lambda: ["component_id"])


class ObsidianConfig(BaseModel):
    vault_path: str = ""
    sync_mode: Literal["filesystem", "rest-api"] = "filesystem"
    rest_api: ObsidianRestConfig = Field(default_factory=ObsidianRestConfig)
    transform: ObsidianTransformConfig = Field(default_factory=ObsidianTransformConfig)
    mapping: ObsidianMappingConfig = Field(default_factory=ObsidianMappingConfig)


class ChroniclerConfig(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    vcs: VCSConfig = Field(default_factory=VCSConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    monorepo: MonorepoConfig = Field(default_factory=MonorepoConfig)
    document_conversion: DocumentConversionConfig = Field(default_factory=DocumentConversionConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    merkle: MerkleConfig = Field(default_factory=MerkleConfig)
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    log_level: Literal["debug", "info", "warn", "error"] = "info"
    log_format: Literal["text", "json"] = "text"
