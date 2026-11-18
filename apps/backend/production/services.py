from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions

from orders.models import Order
from organizations.models import Membership, Organization

from .models import ProductionTask

CHECKLISTS_BY_CATEGORY: dict[str, list[tuple[str, str, int]]] = {
    Organization.Category.TAILOR: [
        ("Pattern & fabric cutting", ProductionTask.Stage.CUTTING, 1),
        ("Main sewing & assembly", ProductionTask.Stage.SEWING, 2),
        ("First fitting check", ProductionTask.Stage.FITTING, 3),
        ("Finishing, hemming & pressing", ProductionTask.Stage.FINISHING, 4),
        ("Final quality inspection", ProductionTask.Stage.QUALITY_CHECK, 5),
    ],
    Organization.Category.SHOEMAKER: [
        ("Last selection & sole pattern", ProductionTask.Stage.CUTTING, 1),
        ("Upper leather cutting & skiving", ProductionTask.Stage.CUTTING, 2),
        ("Closing & upper stitching", ProductionTask.Stage.SEWING, 3),
        ("Lasting, soling & heel build", ProductionTask.Stage.FINISHING, 4),
        ("Trial fitting & polish check", ProductionTask.Stage.QUALITY_CHECK, 5),
    ],
    Organization.Category.LEATHERWORKER: [
        ("Template & hide cutting", ProductionTask.Stage.CUTTING, 1),
        ("Skiving & hardware prep", ProductionTask.Stage.SEWING, 2),
        ("Saddle stitching & assembly", ProductionTask.Stage.SEWING, 3),
        ("Edge beveling, burnishing & paint", ProductionTask.Stage.FINISHING, 4),
        ("Monogram & final quality check", ProductionTask.Stage.QUALITY_CHECK, 5),
    ],
    Organization.Category.OTHER: [
        ("Material & pattern preparation", ProductionTask.Stage.CUTTING, 1),
        ("Primary crafting & assembly", ProductionTask.Stage.SEWING, 2),
        ("Client check / fitting", ProductionTask.Stage.FITTING, 3),
        ("Finishing & detailing", ProductionTask.Stage.FINISHING, 4),
        ("Final quality inspection", ProductionTask.Stage.QUALITY_CHECK, 5),
    ],
}


def validate_task_relations(*, organization, order: Order, assigned_to=None):
    if order.organization_id != organization.id:
        raise exceptions.PermissionDenied("Order does not belong to the active organization.")
    if assigned_to is not None:
        is_member = Membership.objects.filter(
            organization=organization,
            user=assigned_to,
            status=Membership.Status.ACTIVE,
        ).exists()
        if not is_member:
            raise exceptions.ValidationError(
                {"assigned_to": "Assigned user must be an active member of this organization."}
            )


@transaction.atomic
def seed_standard_checklist(*, organization, order: Order, actor) -> list[ProductionTask]:
    if order.organization_id != organization.id:
        raise exceptions.PermissionDenied("Order does not belong to the active organization.")
    checklist = CHECKLISTS_BY_CATEGORY.get(
        organization.category,
        CHECKLISTS_BY_CATEGORY[Organization.Category.TAILOR],
    )
    existing_titles = set(order.production_tasks.values_list("title", flat=True))
    created: list[ProductionTask] = []
    for title, stage, display_order in checklist:
        if title in existing_titles:
            continue
        task = ProductionTask.objects.create(
            organization=organization,
            order=order,
            title=title,
            stage=stage,
            status=ProductionTask.Status.TODO,
            display_order=display_order,
            assigned_to=order.assigned_to,
            created_by=actor,
        )
        created.append(task)
    return created


def apply_task_status_timestamp(task: ProductionTask, new_status: str):
    if new_status == ProductionTask.Status.DONE and task.completed_at is None:
        task.completed_at = timezone.now()
    elif new_status != ProductionTask.Status.DONE and task.completed_at is not None:
        task.completed_at = None
