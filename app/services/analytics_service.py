from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from datetime import datetime, timedelta, date
from app.models.chat_user_message_count import ChatUserMessageCount
from app.models.bot_user import BotUser
from app.models.banned_user import BannedUser

class AnalyticsService:
    @classmethod
    def get_analytics_for_period(
        cls,
        db: Session,
        bot_id: int,
        period: str = "all_time"
    ) -> Dict[str, Any]:
        now = datetime.utcnow()
        today = date.today()

        if period == "1_day":
            start_date = today - timedelta(days=1)
        elif period == "1_week":
            start_date = today - timedelta(weeks=1)
        elif period == "1_month":
            start_date = today - timedelta(days=30)
        elif period == "1_year":
            start_date = today - timedelta(days=365)
        else:  # all_time
            start_date = None

        analytics_data = cls._calculate_analytics(db, bot_id, start_date, today)
        return analytics_data

    @classmethod
    def _calculate_analytics(
        cls,
        db: Session,
        bot_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, int]:
        if end_date is None:
            end_date = date.today()

        total_messages = ChatUserMessageCount.get_total_messages_for_period(
            db, bot_id, start_date, end_date
        )
        total_chats = ChatUserMessageCount.get_unique_chats_for_period(
            db, bot_id, start_date, end_date
        )

        user_query = db.query(
            func.count(distinct(BotUser.user_id))
        ).filter(BotUser.bot_id == bot_id)
        if start_date:
            user_query = user_query.filter(BotUser.first_interaction >= datetime.combine(start_date, datetime.min.time()))
        unique_users = user_query.scalar() or 0

        banned_query = db.query(
            func.count(BannedUser.id)
        ).filter(
            BannedUser.bot_id == bot_id,
            BannedUser.is_active == True
        )
        if start_date:
            banned_query = banned_query.filter(BannedUser.banned_at >= datetime.combine(start_date, datetime.min.time()))
        banned_users = banned_query.scalar() or 0

        return {
            'total_chats': total_chats,
            'total_messages': total_messages,
            'unique_users': unique_users,
            'banned_users': banned_users
        }

    @classmethod
    def get_all_periods_analytics(
        cls,
        db: Session,
        bot_id: int
    ) -> Dict[str, Any]:
        periods = ["1_day", "1_week", "1_month", "1_year", "all_time"]
        analytics = {}
        for period in periods:
            analytics[period] = cls.get_analytics_for_period(db, bot_id, period)
        return analytics

    @classmethod
    def get_trend_data(
        cls,
        db: Session,
        bot_id: int,
        period: str = "all_time",
        data_type: str = "messages"
    ) -> Dict[str, Any]:
        """
        Get trend data for charts.
        Args:
            db: Database session
            bot_id: Bot ID
            period: Time period ('1_day', '1_week', '1_month', '1_year', 'all_time')
            data_type: Type of data ('messages', 'chats', 'users', 'banned_users')
        Returns:
            Dict with dates and values for charting
        """
        now = datetime.utcnow()
        today = date.today()

        if period == "1_day":
            start_date = today - timedelta(days=1)
            interval = timedelta(hours=1)
        elif period == "1_week":
            start_date = today - timedelta(weeks=1)
            interval = timedelta(days=1)
        elif period == "1_month":
            start_date = today - timedelta(days=30)
            interval = timedelta(days=1)
        elif period == "1_year":
            start_date = today - timedelta(days=365)
            interval = timedelta(days=7)
        else:  # all_time
            start_date = today - timedelta(days=365)  # Default to 1 year for all_time
            interval = timedelta(days=30)

        dates = []
        values = []

        current_date = start_date
        while current_date <= today:
            if data_type == "messages":
                value = ChatUserMessageCount.get_total_messages_for_period(
                    db, bot_id, current_date, current_date
                )
            elif data_type == "chats":
                value = ChatUserMessageCount.get_unique_chats_for_period(
                    db, bot_id, current_date, current_date
                )
            elif data_type == "users":
                # For users, we'll count unique users who had interactions on this date
                from app.models.bot_user import BotUser
                user_query = db.query(
                    func.count(func.distinct(BotUser.user_id))
                ).filter(BotUser.bot_id == bot_id)
                if current_date:
                    user_query = user_query.filter(
                        BotUser.first_interaction >= datetime.combine(current_date, datetime.min.time()),
                        BotUser.first_interaction < datetime.combine(current_date + timedelta(days=1), datetime.min.time())
                    )
                value = user_query.scalar() or 0
            elif data_type == "banned_users":
                # For banned users, we'll count bans created on this date
                banned_query = db.query(
                    func.count(BannedUser.id)
                ).filter(
                    BannedUser.bot_id == bot_id,
                    BannedUser.is_active == True
                )
                if current_date:
                    banned_query = banned_query.filter(
                        BannedUser.banned_at >= datetime.combine(current_date, datetime.min.time()),
                        BannedUser.banned_at < datetime.combine(current_date + timedelta(days=1), datetime.min.time())
                    )
                value = banned_query.scalar() or 0
            else:
                value = 0

            dates.append(current_date.strftime("%Y-%m-%d"))
            values.append(value)
            
            current_date += interval

        return {
            "dates": dates,
            "values": values,
            "data_type": data_type,
            "period": period
        } 