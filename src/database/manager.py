import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from src.core.config import config
from datetime import datetime
from typing import AsyncGenerator, List, Optional, Sequence
from sqlalchemy import select, update, and_
from src.database.models import Base, User, Service, Request, Admin

logger = logging.getLogger("checker-bot.database")

class DatabaseManager:
    """Manages asynchronous database connections and sessions."""

    def __init__(self, db_url: str):
        self.engine = create_async_engine(
            db_url,
            echo=False,  # Set to True for SQL debugging
            future=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self):
        """Initializes the database and creates all tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provides an asynchronous session context manager."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    # --- User Methods ---

    async def get_or_create_user(self, tg_id: int, first_name: str, username: Optional[str]) -> User:
        """Retrieves or creates a user based on their Telegram ID."""
        async with self.get_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == tg_id))
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    telegram_id=tg_id,
                    first_name=first_name,
                    username=username
                )
                session.add(user)
                await session.flush()
                logger.info(f"Created new user: {tg_id}")
            else:
                # Update info if it changed
                user.first_name = first_name
                user.username = username
                user.last_seen = datetime.now()
            
            return user

    async def update_last_seen(self, tg_id: int):
        """Updates the last_seen timestamp for a user."""
        async with self.get_session() as session:
            await session.execute(
                update(User)
                .where(User.telegram_id == tg_id)
                .values(last_seen=datetime.now())
            )

    # --- Service Methods ---

    async def get_active_services(self) -> Sequence[Service]:
        """Returns a list of all active services."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Service).where(Service.is_active == True)
            )
            return result.scalars().all()

    async def get_service_by_id(self, service_id: int) -> Optional[Service]:
        """Retrieves a service by its ID."""
        async with self.get_session() as session:
            result = await session.execute(select(Service).where(Service.id == service_id))
            return result.scalar_one_or_none()

    async def get_all_services(self) -> Sequence[Service]:
        """
        Returns all services including disabled ones.
        Ordered by ID ascending.
        """
        async with self.get_session() as session:
            result = await session.execute(
                select(Service).order_by(Service.id.asc())
            )
            return result.scalars().all()

    # --- Request Methods ---

    async def check_duplicate_request(self, service_id: int, mobile_number: str) -> bool:
        """
        Checks if an active (PENDING or PROCESSING) request already exists 
        for the same service and mobile number across ALL users.
        """
        async with self.get_session() as session:
            result = await session.execute(
                select(Request).where(
                    and_(
                        Request.service_id == service_id,
                        Request.mobile_number == mobile_number,
                        Request.status.in_(["PENDING", "PROCESSING"])
                    )
                )
            )
            return result.scalar_one_or_none() is not None

    async def create_request(self, user_id: int, service_id: int, mobile_number: str, is_bulk: bool = False, extra_data: Optional[str] = None) -> Request:
        """Creates a new request in the database."""
        async with self.get_session() as session:
            request = Request(
                user_id=user_id,
                service_id=service_id,
                mobile_number=mobile_number,
                status="PENDING",
                is_bulk=is_bulk,
                extra_data=extra_data
            )
            session.add(request)
            
            # Increment service request counter
            await session.execute(
                update(Service)
                .where(Service.id == service_id)
                .values(total_requests=Service.total_requests + 1)
            )
            
            await session.flush()
            return request

    async def get_request_by_id(self, request_id: int) -> Optional[Request]:
        """Retrieves a request by its ID."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Request).where(Request.id == request_id)
            )
            return result.scalar_one_or_none()

    async def update_request_status(self, request_id: int, status: str):
        """Updates the status of a request."""
        async with self.get_session() as session:
            await session.execute(
                update(Request)
                .where(Request.id == request_id)
                .values(status=status, updated_at=datetime.now())
            )

    async def store_group_message_id(self, request_id: int, group_message_id: int):
        """Stores the Telegram message ID of the request sent to the service group."""
        async with self.get_session() as session:
            await session.execute(
                update(Request)
                .where(Request.id == request_id)
                .values(group_message_id=group_message_id, updated_at=datetime.now())
            )

    async def store_user_message_id(self, request_id: int, user_message_id: int):
        """Stores the Telegram message ID of the receipt sent to the user."""
        async with self.get_session() as session:
            await session.execute(
                update(Request)
                .where(Request.id == request_id)
                .values(user_message_id=user_message_id, updated_at=datetime.now())
            )

    async def get_request_by_group_message_id(self, group_id: int, message_id: int) -> Optional[Request]:
        """Retrieves a pending or processing request by the message ID it was sent as in a group."""
        async with self.get_session() as session:
            result = await session.execute(
                select(Request)
                .join(Service)
                .where(
                    and_(
                        Service.group_id == group_id,
                        Request.group_message_id == message_id,
                        Request.status.in_(["PENDING", "PROCESSING"])
                    )
                )
            )
            return result.scalar_one_or_none()

    async def find_matching_request(self, group_id: int, mobile_number: str) -> Optional[Request]:
        """
        Finds a pending or processing request matching the group_id and mobile number.
        Supports multiple services sharing the same group.
        """
        async with self.get_session() as session:
            # Join Request and Service to find a request where the associated service has the target group_id
            request_result = await session.execute(
                select(Request)
                .join(Service)
                .where(
                    and_(
                        Service.group_id == group_id,
                        Request.mobile_number == mobile_number,
                        Request.status.in_(["PENDING", "PROCESSING"])
                    )
                ).order_by(Request.created_at.desc())
            )
            request = request_result.scalars().first()

            if request:
                logger.info(
                    f"[MATCH DEBUG]\n"
                    f"Group ID: {group_id}\n"
                    f"Mobile: {mobile_number}\n"
                    f"Request ID: {request.id}\n"
                    f"Service ID: {request.service_id}"
                )
            
            return request

    async def complete_request(self, request_id: int, result_text: str):
        """Marks a request as completed and stores the result."""
        async with self.get_session() as session:
            await session.execute(
                update(Request)
                .where(Request.id == request_id)
                .values(
                    status="COMPLETED",
                    result_text=result_text,
                    completed_at=datetime.now(),
                    updated_at=datetime.now()
                )
            )

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Retrieves a user by their internal database ID."""
        async with self.get_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Retrieves a user by their Telegram ID."""
        async with self.get_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            return result.scalar_one_or_none()

    # --- Admin Methods ---

    async def is_admin(self, tg_id: int) -> bool:
        """Checks if a user is an authorized admin."""
        if tg_id in config.ADMIN_IDS:
            return True
        
        async with self.get_session() as session:
            result = await session.execute(
                select(Admin).where(and_(Admin.telegram_id == tg_id, Admin.is_active == True))
            )
            return result.scalar_one_or_none() is not None

    async def get_admin_stats(self) -> dict:
        """Retrieves system-wide statistics for the admin dashboard."""
        async with self.get_session() as session:
            from sqlalchemy import func
            
            user_count = await session.execute(select(func.count(User.id)))
            service_count = await session.execute(select(func.count(Service.id)).where(Service.is_active == True))
            
            # Request counts by status
            pending = await session.execute(select(func.count(Request.id)).where(Request.status == "PENDING"))
            processing = await session.execute(select(func.count(Request.id)).where(Request.status == "PROCESSING"))
            completed = await session.execute(select(func.count(Request.id)).where(Request.status == "COMPLETED"))
            failed = await session.execute(select(func.count(Request.id)).where(Request.status == "FAILED"))
            
            # Requests today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_reqs = await session.execute(
                select(func.count(Request.id)).where(Request.created_at >= today_start)
            )

            return {
                "total_users": user_count.scalar(),
                "active_services": service_count.scalar(),
                "pending": pending.scalar(),
                "processing": processing.scalar(),
                "completed": completed.scalar(),
                "failed": failed.scalar(),
                "requests_today": today_reqs.scalar()
            }

    async def create_service(self, name: str, group_id: int, reply_to_message_id: Optional[int] = None, message_link: Optional[str] = None) -> Service:
        """Creates a new service."""
        async with self.get_session() as session:
            service = Service(
                name=name,
                group_id=group_id,
                reply_to_message_id=reply_to_message_id,
                message_link=message_link
            )
            session.add(service)
            await session.flush()
            return service

    async def update_service(self, service_id: int, **kwargs):
        """Updates service fields (name, group_id, is_active, etc.)."""
        async with self.get_session() as session:
            await session.execute(
                update(Service)
                .where(Service.id == service_id)
                .values(**kwargs, updated_at=datetime.now())
            )

    async def delete_service(self, service_id: int):
        """Deletes a service (Hard delete)."""
        async with self.get_session() as session:
            from sqlalchemy import delete
            await session.execute(delete(Service).where(Service.id == service_id))

    async def toggle_user_ban(self, telegram_id: int) -> bool:
        """Toggles the banned status of a user. Returns new status."""
        async with self.get_session() as session:
            user = await self.get_user_by_telegram_id(telegram_id)
            if user:
                user.is_banned = not user.is_banned
                return user.is_banned
            return False

    async def get_all_users(self) -> Sequence[User]:
        """Returns all non-banned users."""
        async with self.get_session() as session:
            result = await session.execute(
                select(User).where(User.is_banned == False)
            )
            return result.scalars().all()

    async def close(self):
        """Closes the database engine."""
        await self.engine.dispose()
        logger.info("Database engine closed.")


# Global instance of DatabaseManager
db_manager = DatabaseManager(config.DATABASE_URL)
