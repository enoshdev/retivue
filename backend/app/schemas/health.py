from pydantic import BaseModel, Field


class BackendHealthResponse(BaseModel):
    status: str = Field(..., description="Overall backend service status", json_schema_extra={"example": "healthy"})
    project: str = Field(..., description="Project name", json_schema_extra={"example": "RETIVUE Clinical Backend"})
    environment: str = Field(..., description="Current deployment environment", json_schema_extra={"example": "development"})
    version: str = Field("1.0.0", description="API version")


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., description="Database connection health ('healthy' or 'unhealthy')")
    database: str = Field(..., description="Connectivity state ('connected' or 'disconnected')")
    latency_ms: float = Field(..., description="Ping latency in milliseconds")
    message: str = Field(..., description="Diagnostic message")
