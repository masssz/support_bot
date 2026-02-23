from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, select, update
from config import DATABASE_URL

Base = declarative_base()
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------- МОДЕЛИ ----------

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    is_admin = Column(Boolean, default=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    admin_id = Column(BigInteger, nullable=True)
    status = Column(String, default="open")


# ---------- ИНИЦИАЛИЗАЦИЯ ----------

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------- USER ----------

async def get_user(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


async def create_user(user_id, is_admin=False):
    async with async_session() as session:
        user = User(id=user_id, is_admin=is_admin)
        session.add(user)
        await session.commit()


# ---------- TICKET ----------

async def create_ticket(user_id):
    async with async_session() as session:
        ticket = Ticket(user_id=user_id)
        session.add(ticket)
        await session.commit()
        return ticket.id


async def assign_ticket(ticket_id, admin_id):
    async with async_session() as session:
        await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(status="in_progress", admin_id=admin_id)
        )
        await session.commit()


async def close_ticket(ticket_id):
    async with async_session() as session:
        await session.execute(
            update(Ticket)
            .where(Ticket.id == ticket_id)
            .values(status="closed")
        )
        await session.commit()


async def get_ticket(ticket_id):
    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()


async def get_active_ticket_by_user(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(Ticket).where(
                Ticket.user_id == user_id,
                Ticket.status != "closed"
            )
        )
        return result.scalar_one_or_none()


async def get_all_tickets():
    async with async_session() as session:
        result = await session.execute(select(Ticket))
        return result.scalars().all()