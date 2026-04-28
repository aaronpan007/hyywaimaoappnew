"""Seed script: insert test data for development.

Run: cd backend && PYTHONUTF8=1 python -m app.seed
Requires: PostgreSQL running with database created
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.models import Base, User, UserSettings, Task, TaskLog, Lead, CompanyProfile, OutreachEmail


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if user 1 already exists
        result = await db.execute(select(User).where(User.id == 1))
        if result.scalar_one_or_none():
            print("Seed data already exists, skipping.")
            return

        # 1. User (no FK deps)
        user = User(id=1, username="demo")
        db.add(user)
        await db.flush()

        # 2. UserSettings (FK → users)
        settings = UserSettings(
            id=1,
            user_id=1,
            sender_name="张经理",
            from_email_prefix="zhangmanager",
            reply_to_email="zhang@example.com",
        )
        db.add(settings)
        await db.flush()

        # 3. CompanyProfile (FK → users, task_id nullable)
        profile_data = {
            "companyName": "深圳市光明科技有限公司",
            "industry": "电子元器件",
            "website": "www.gmtech.com",
            "established": "2015年",
            "employees": "50-100人",
            "certifications": "ISO 9001, CE, RoHS",
            "cooperationModels": "OEM, ODM",
            "products": ["LED驱动电源", "智能控制器", "传感器模块"],
            "competencies": ["自主研发", "快速交付", "定制化方案"],
            "caseStudies": [
                {"project": "欧洲智能家居项目", "description": "为德国客户定制智能家居控制系统，年出货量10万套"},
                {"project": "美国LED照明项目", "description": "提供高效率LED驱动方案，通过UL认证"},
            ],
        }
        profile = CompanyProfile(
            id=1,
            user_id=1,
            company_name="深圳市光明科技有限公司",
            profile_data=profile_data,
            profile_markdown="# 深圳市光明科技有限公司\n\n成立于2015年...",
            is_current=True,
        )
        db.add(profile)
        await db.flush()

        # Link settings to profile
        settings.profile_id = profile.id
        await db.flush()

        # 4. Tasks (FK → users)
        task1 = Task(
            id=1,
            user_id=1,
            type="customer-acquisition",
            status="completed",
            params={"industry": "Solar Panels", "country": "USA", "count": 30},
            result_summary={"found": 25, "avgScore": 82},
        )
        task2 = Task(
            id=2,
            user_id=1,
            type="company-profile",
            status="completed",
            params={"website": "www.gmtech.com"},
            result_summary={"status": "success"},
        )
        db.add_all([task1, task2])
        await db.flush()

        # 5. TaskLogs (FK → tasks)
        logs1 = [
            TaskLog(id=1, task_id=1, step_number=1, step_name="分析需求", status="completed", message="需求分析完成", progress=100),
            TaskLog(id=2, task_id=1, step_number=2, step_name="搜索公司数据", status="completed", message="已搜索 50 家公司", progress=100),
            TaskLog(id=3, task_id=1, step_number=3, step_name="AI 分析匹配", status="completed", message="AI 分析完成", progress=100),
            TaskLog(id=4, task_id=1, step_number=4, step_name="生成线索报告", status="completed", message="报告生成完成", progress=100),
        ]
        logs2 = [
            TaskLog(id=5, task_id=2, step_number=1, step_name="抓取网站", status="completed", message="网站抓取完成", progress=100),
            TaskLog(id=6, task_id=2, step_number=2, step_name="AI 分析", status="completed", message="AI 分析完成", progress=100),
            TaskLog(id=7, task_id=2, step_number=3, step_name="生成画像", status="completed", message="画像生成完成", progress=100),
        ]
        db.add_all(logs1 + logs2)
        await db.flush()

        # 6. Leads (FK → tasks)
        leads = [
            Lead(id=1, task_id=1, company_name="SolarTech USA", website="www.solartechusa.com", country="United States", industry="Solar Energy", company_role="Distributor", contact_name="John Smith", email="john@solartechusa.com", phone="+1-555-0101", ai_summary="美国大型太阳能分销商，覆盖全美市场", business_match="对LED驱动电源有需求", outreach_suggestion="建议从智能家居控制切入", match_score=92),
            Lead(id=2, task_id=1, company_name="GreenPower Solutions", website="www.greenpower.com", country="United States", industry="Renewable Energy", company_role="Integrator", contact_name="Sarah Johnson", email="sarah@greenpower.com", phone="+1-555-0102", ai_summary="可再生能源系统集成商", business_match="需要智能控制器方案", outreach_suggestion="可提供定制化控制方案", match_score=88),
            Lead(id=3, task_id=1, company_name="Pacific Solar Supply", website="www.pacificsolar.com", country="United States", industry="Solar Wholesale", company_role="Wholesaler", contact_name="Mike Chen", email="mike@pacificsolar.com", phone="+1-555-0103", ai_summary="太平洋地区太阳能批发商", business_match="批量采购传感器模块", outreach_suggestion="提供OEM合作方案", match_score=85),
            Lead(id=4, task_id=1, company_name="EcoLight Distributors", website="www.ecolight.com", country="Germany", industry="LED Lighting", company_role="Distributor", contact_name="Hans Mueller", email="hans@ecolight.com", phone="+49-30-123456", ai_summary="德国LED照明分销商", business_match="LED驱动电源直接匹配", outreach_suggestion="强调CE认证和高效能", match_score=90),
            Lead(id=5, task_id=1, company_name="SmartHome EU", website="www.smarthome-eu.com", country="Germany", industry="Smart Home", company_role="System Integrator", contact_name="Anna Schmidt", email="anna@smarthome-eu.com", phone="+49-89-789012", ai_summary="欧洲智能家居集成商", business_match="智能控制器需求高度匹配", outreach_suggestion="展示智能家居案例", match_score=87),
        ]
        db.add_all(leads)
        await db.flush()

        # 7. OutreachEmails (FK → leads, tasks)
        emails = [
            OutreachEmail(id=1, lead_id=1, task_id=1, email_subject="Partnership Opportunity - Smart Lighting Solutions", email_body="<p>Dear John,</p><p>We specialize in LED driver solutions...</p>", send_status="sent", sent_at=datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)),
            OutreachEmail(id=2, lead_id=2, task_id=1, email_subject="Custom Control Solutions for GreenPower", email_body="<p>Dear Sarah,</p><p>Our smart controllers could enhance...</p>", send_status="sent", sent_at=datetime(2026, 4, 25, 10, 5, tzinfo=timezone.utc)),
            OutreachEmail(id=3, lead_id=3, task_id=1, email_subject="OEM Partnership - Sensor Modules", email_body="<p>Dear Mike,</p><p>We offer high-quality sensor modules...</p>", send_status="draft"),
            OutreachEmail(id=4, lead_id=4, task_id=1, email_subject="LED Driver Solutions with CE Certification", email_body="<p>Dear Hans,</p><p>Our CE-certified LED drivers...</p>", send_status="pending"),
            OutreachEmail(id=5, lead_id=5, task_id=1, email_subject="Smart Home Control Partnership", email_body="<p>Dear Anna,</p><p>Our smart home controllers...</p>", send_status="draft"),
        ]
        db.add_all(emails)

        await db.commit()
        print("Seed data inserted successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
