from typing import Annotated, cast

from fastapi import Depends, Request

from velvetdub.container import Container
from velvetdub.domain.user import User


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


ContainerDep = Annotated[Container, Depends(get_container)]


def get_current_user(request: Request, container: ContainerDep) -> User:
    return container.identity.current_user(request)


CurrentUser = Annotated[User, Depends(get_current_user)]
