import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.proposals as proposals_service
from app.auth.deps import current_active_user
from app.database import get_db
from app.models.user import User
from app.schemas.proposals import ProposalRead

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.post("/{proposal_id}/confirm", response_model=ProposalRead)
async def confirm_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        return await proposals_service.confirm(db, current_user.id, proposal_id)
    except proposals_service.ProposalNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposition introuvable")
    except proposals_service.ProposalForbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
    except proposals_service.ProposalAlreadyCancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette proposition a déjà été annulée",
        )
    except proposals_service.ProposalExecutionFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )


@router.post("/{proposal_id}/cancel", response_model=ProposalRead)
async def cancel_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(current_active_user),
):
    try:
        return await proposals_service.cancel(db, current_user.id, proposal_id)
    except proposals_service.ProposalNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposition introuvable")
    except proposals_service.ProposalForbidden:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
