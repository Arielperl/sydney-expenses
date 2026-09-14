"""Request-scoped ORM isolation, including aggregate queries and bulk deletes.
Administrative sessions remain explicit; request sessions must have a tenant.
"""
from sqlalchemy import event, inspect
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.orm import Session, with_loader_criteria
from app.models.business import BusinessOwned

@event.listens_for(Session, "do_orm_execute")
def scope_statement(state):
    business_id = state.session.info.get("business_id")
    if not business_id:
        return
    if isinstance(state.statement, TextClause):
        raise ValueError("Raw SQL is not allowed in a business-scoped session")
    if state.is_insert:
        raise ValueError("Bulk ORM inserts are not allowed in a business-scoped session")
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(with_loader_criteria(
            BusinessOwned, lambda cls: cls.business_id == business_id, include_aliases=True))

@event.listens_for(Session, "before_flush")
def scope_writes(session, context, instances):
    business_id = session.info.get("business_id")
    if not business_id:
        return
    for obj in session.new | session.dirty | session.deleted:
        if isinstance(obj, BusinessOwned):
            if obj in session.new and obj.business_id is None:
                obj.business_id = business_id
            if obj.business_id != business_id:
                raise ValueError("Cross-business write rejected")
            if obj not in session.new and inspect(obj).attrs.business_id.history.has_changes():
                raise ValueError("Business ownership is immutable")
