from pydantic import BaseModel, Field
from typing import Literal


class LLMConfig(BaseModel):
    provider: Literal["anthropic", "openai", "google"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_tokens: int = 4096
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0


class QueueConfig(BaseModel):
    provider: Literal["sqs", "pubsub", "servicebus", "local"] = "local"
    url: str | None = None
    dlq_url: str | None = None
    max_workers: int = 5
    visibility_timeout: int = 300


class VCSConfig(BaseModel):
    provider: Literal["github", "azure", "gitlab"] = "github"
    token_env: str = "GITHUB_TOKEN"
    allowed_orgs: list[str] = []
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
    max_file_size_mb: int = 50
    max_pages: int = 100
    cache: DocCacheConfig = Field(default_factory=DocCacheConfig)


class PluginsConfig(BaseModel):
    queue: str | None = None
    graph: str | None = None
    rbac: str | None = None
    storage: str | None = None


class ChroniclerConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    vcs: VCSConfig = Field(default_factory=VCSConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    monorepo: MonorepoConfig = Field(default_factory=MonorepoConfig)
    document_conversion: DocumentConversionConfig = Field(default_factory=DocumentConversionConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    log_level: Literal["debug", "info", "warn", "error"] = "info"
    log_format: Literal["text", "json"] = "text"
