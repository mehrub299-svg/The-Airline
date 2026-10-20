from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.services import feature_flags

router = APIRouter(prefix="/flags", tags=["flags"])


@router.get("", response_model=dict[str, bool])
async def list_flags(current_user: User = Depends(get_current_user)):
    return await feature_flags.effective_flags(current_user.tenant_id)