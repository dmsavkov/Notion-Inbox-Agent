"""
Manual test script to verify task creation works with actual Notion API.
Run this to test the complete task creation flow.
"""
from notion_client import Client
from inbox_agent.config import settings
from inbox_agent.pydantic_models import NotionTask, AIUseStatus
from inbox_agent.task import TaskManager


def test_task_creation():
    """Test creating a task in the actual Notion database"""
    
    print("🔧 Initializing Notion client...")
    client = Client(auth=settings.NOTION_TOKEN)
    task_manager = TaskManager(client)
    
    # Create a test task
    test_task = NotionTask(
        title="Test Task from API - Delete Me",
        projects=["General Individual Qualities"],  # Use a project from your workspace
        ai_use_status=AIUseStatus.PROCESSED,
        importance=2,
        urgency=1,
        impact=50,
        original_note="This is a test note created via the API. You can safely delete this task.",
        enrichment="Test enrichment: This task was created to verify the API integration works correctly."
    )
    
    print(f"📝 Creating task: {test_task.title}")
    print(f"   Properties:")
    print(f"   - Importance: {test_task.importance}")
    print(f"   - Urgency: {test_task.urgency}")
    print(f"   - Impact Score: {test_task.impact}")
    print(f"   - UseAIStatus: {test_task.ai_use_status.value}")
    print(f"   - Status: Not started")
    print(f"   - Project: {test_task.projects[0]}")
    
    try:
        result = task_manager.create_task(test_task)
        print(f"\n✅ Task created successfully!")
        print(f"   Task ID: {result['id']}")
        print(f"   URL: {result.get('url', 'N/A')}")
        return result
    
    except Exception as e:
        print(f"\n❌ Failed to create task: {e}")
        print("\nPossible issues:")
        print("1. Make sure the Tasks database is shared with your integration")
        print("2. Verify NOTION_TASKS_DATA_SOURCE_ID is correct in .env")
        print("3. Ensure property names match your Notion database schema")
        print("4. Check that the project 'General Individual Qualities' exists")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Notion Task Creation")
    print("=" * 60)
    result = test_task_creation()
    print("\n" + "=" * 60)
    print("Test completed! Check your Notion tasks database.")
    print("=" * 60)
