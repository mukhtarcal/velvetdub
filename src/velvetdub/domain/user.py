"""Users. Today there is one fixed local user; every owned record already carries an owner id."""

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str


LOCAL_USER = User(id="local", display_name="You")
