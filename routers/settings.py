"""설정 관리 API."""
from fastapi import APIRouter, Body
from repos import settings_repo

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    """전체 설정 조회."""
    return settings_repo.get_all()


@router.put("/{key}")
def update_setting(key: str, value=Body(..., embed=True)):
    """개별 설정 변경."""
    settings_repo.set(key, value)
    return {"status": "ok", "key": key}


@router.post("/reset")
def reset_settings():
    """모든 설정을 초기값으로 리셋."""
    settings_repo.reset_all()
    return {"status": "ok"}
