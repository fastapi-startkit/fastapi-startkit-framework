from app.agents.support_agent import SupportAgent


async def test_answers_order_status():
    with SupportAgent.fake(['{"order_id": 1042, "status": "shipped"}']):
        response = await SupportAgent().prompt("Where is order #1042?")

    assert response["structured_response"].status == "shipped"
