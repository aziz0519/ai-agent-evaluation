from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import ToolCall

dataset = EvaluationDataset(
    goldens=[
        Golden(
            input="I am user123, I would like a refund for the book and the pen",
            expected_output="A refund ticket for 30$ has been issued successfully",
            expected_tools=[
                ToolCall(
                    name="get_user_purchase_history",
                    input_parameters={"user": "user123"}),
                ToolCall(
                    name="get_today_date",
                    input_parameters={}
                ),
                ToolCall(name="calculate_right_refund", 
                         input_parameters={}
                ),
                ToolCall(name="issue_refund_ticket", 
                         input_parameters={"user": "user123", "refund_amount": 123})
            ]
        )
    ]
)