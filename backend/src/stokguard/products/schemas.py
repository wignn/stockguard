from pydantic import BaseModel, ConfigDict, Field, field_validator

from stokguard.core.numbers import parse_quantity, parse_rupiah


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=30)
    step_quantity: str
    cost_rupiah: str

    @field_validator("sku", "name", "unit")
    @classmethod
    def trim_text(cls, value: str, info):
        value = value.strip()
        if not value:
            raise ValueError("Isian tidak boleh kosong.")
        return value.upper() if info.field_name == "sku" else value

    @field_validator("step_quantity")
    @classmethod
    def valid_step(cls, value: str):
        if parse_quantity(value, 1) < 1:
            raise ValueError("Langkah satuan minimal 0.001.")
        return value

    @field_validator("cost_rupiah")
    @classmethod
    def valid_cost(cls, value: str):
        parse_rupiah(value)
        return value


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    sku: str | None = None
    name: str | None = None
    unit: str | None = None
    step_quantity: str | None = None
    cost_rupiah: str | None = None
    active: bool | None = Field(default=None, strict=True)


class ProductView(BaseModel):
    id: str
    business_id: str
    sku: str
    name: str
    unit: str
    step_quantity: str
    cost_rupiah: str
    active: bool
    version: int
    balance_quantity: str
    balance_version: int
