import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from openai.types.beta import Thread
from openai.types.beta.threads import (
    MessageContentImageFile,
    MessageContentText,
    ThreadMessage,
)
from openai.types.beta.threads.runs import RunStep
from openai.types.beta.threads.runs.tool_calls_step_details import ToolCall

from chainlit.element import Element
import chainlit as cl

#设置代理
import os

os.environ['http_proxy'] = 'http://127.0.0.1:10809'
os.environ['https_proxy'] = 'http://127.0.0.1:10809'

def get_current_weather(location: str, format: str):
    # return dummy weather
    return "The current weather in {} is {} degrees {}".format(location, 20, format)


def get_n_day_weather_forecast(location: str, format: str, num_days: int):
    # return dummy weather
    return "The weather forecast for the next {} days in {} is {} degrees {}".format(
        num_days, location, 20, format
    )


tool_map = {
    "get_current_weather": get_current_weather,
    "get_n_day_weather_forecast": get_n_day_weather_forecast,
}

api_key = os.environ.get("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)


# List of allowed mime types
allowed_mime = ["text/csv", "application/pdf"]


# Check if the files uploaded are allowed
async def check_files(files: List[Element]):
    for file in files:
        if file.mime not in allowed_mime:
            return False
    return True


# Upload files to the assistant
async def upload_files(files: List[Element]):
    file_ids = []
    for file in files:
        uploaded_file = await client.files.create(
            file=Path(file.path), purpose="assistants"
        )
        file_ids.append(uploaded_file.id)
    return file_ids


async def process_files(files: List[Element]):
    # Upload files if any and get file_ids
    file_ids = []
    if len(files) > 0:
        files_ok = await check_files(files)

        if not files_ok:
            file_error_msg = f"Hey, it seems you have uploaded one or more files that we do not support currently, please upload only : {(',').join(allowed_mime)}"
            await cl.Message(content=file_error_msg).send()
            return file_ids

        file_ids = await upload_files(files)

    return file_ids


async def process_thread_message(
    message_references: Dict[str, cl.Message], thread_message: ThreadMessage
):
    for idx, content_message in enumerate(thread_message.content):
        id = thread_message.id + str(idx)
        if isinstance(content_message, MessageContentText):
            if id in message_references:
                msg = message_references[id]
                msg.content = content_message.text.value
                await msg.update()
            else:
                message_references[id] = cl.Message(
                    author=thread_message.role, content=content_message.text.value
                )
                await message_references[id].send()
        elif isinstance(content_message, MessageContentImageFile):
            image_id = content_message.image_file.file_id
            response = await client.files.with_raw_response.retrieve_content(image_id)
            elements = [
                cl.Image(
                    name=image_id,
                    content=response.content,
                    display="inline",
                    size="large",
                ),
            ]

            if id not in message_references:
                message_references[id] = cl.Message(
                    author=thread_message.role,
                    content="",
                    elements=elements,
                )
                await message_references[id].send()
        else:
            print("unknown message type", type(content_message))


async def process_tool_call(
    step_references: Dict[str, cl.Step],
    step: RunStep,
    tool_call: ToolCall,
    name: str,
    input: Any,
    output: Any,
    show_input: str = None,
):
    cl_step = None
    update = False
    if not tool_call.id in step_references:
        cl_step = cl.Step(
            name=name,
            type="tool",
            parent_id=cl.context.current_step.id,
            show_input=show_input,
        )
        step_references[tool_call.id] = cl_step
    else:
        update = True
        cl_step = step_references[tool_call.id]

    if step.created_at:
        cl_step.start = datetime.fromtimestamp(step.created_at).isoformat()
    if step.completed_at:
        cl_step.end = datetime.fromtimestamp(step.completed_at).isoformat()
    cl_step.input = input
    cl_step.output = output

    if update:
        await cl_step.update()
    else:
        await cl_step.send()


class DictToObject:
    def __init__(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                setattr(self, key, DictToObject(value))
            else:
                setattr(self, key, value)

    def __str__(self):
        return "\n".join(f"{key}: {value}" for key, value in self.__dict__.items())
@cl.oauth_callback
def oauth_callback(
  provider_id: str,
  token: str,
  raw_user_data: Dict[str, str],
  default_user: cl.User,
) -> Optional[cl.User]:
  return default_user

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    # Fetch the user matching username from your database
    # and compare the hashed password with the value stored in the database
    if (username, password) == ("admin", "admin"):
        return cl.User(
            identifier="admin", metadata={"role": "admin", "provider": "credentials"}
        )
    else:
        return None

@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(
            name="assistant1",
            markdown_description="该助手会一步步引导你进行教学设计的前期分析，并且会给你一些不错的建设性意见，适合新手教师使用。",
            icon="./public/k.png",
        ),
        cl.ChatProfile(
            name="assistant2",
            markdown_description="该助手会根据你的需求，协助你完成教学设计，优化教学过程，适合有经验教师使用。",
            icon="./public/g.png",
        ),
        cl.ChatProfile(
            name="assistant3",
            markdown_description="该助手能够为你的教学过程提供思路与灵感，提供各种有创意、符合要求的教学活动。",
            icon="./public/f.png",
        ),
        cl.ChatProfile(
            name="assistant4",
            markdown_description="该助手可以根据你的需要生成符合的教学资源，如ppt、海报、程序、测试题等。",
            icon="./public/k.png",
        ),
        cl.ChatProfile(
            name="assistant5",
            markdown_description="这是学生模拟器，您可以在这里开展模拟课堂，通过虚拟学生对教学活动的反应改进您的教学设计。",
            icon="./public/g.png",
        ),
        cl.ChatProfile(
            name="assistant6",
            markdown_description="这是反思助手，能够协助你反思整个教学流程，总结教育教学经验，促进成长。",
            icon="./public/f.png",
        )
    ]

@cl.on_chat_start
async def start_chat():
    thread = await client.beta.threads.create()
    cl.user_session.set("thread", thread)
    chat_profile = cl.user_session.get("chat_profile")
    if chat_profile =="assistant1":
        content = """
你好！😊我是一位经验丰富的老师，致力于引导和协助学习者通过精心设计的教学活动达成学习目标。在我的职业生涯中，我累积了大量关于如何设计、实施并评估学习活动的经验和知识。我希望能够利用我的经验来帮助你进行教学设计，确保学习者能够在你的课程中获得最佳的学习体验。
在教学设计开发阶段，我会通过下面几个步骤来支持和帮助你：
1.深入讨论和分析: 我会引导你深入探讨和分析教学内容，了解目标学习者的具体情况，包括他们的需求、偏好和背景，以及确定最合适的教学方法来传达内容。
2.结合认知学徒制策略: 我将采用认知学徒制的策略来确保你在教学设计中能有效地结合理论与实践。这包括模仿、指导、教授策略以及鼓励探索和解决问题的技巧。
3.持续的反馈和确认: 在每个设计阶段，我都会通过提问和确认来保证我们的教学设计是按照你的期望和目标前进的。这包括确认教学内容分析、学习情境分析和教学方法的选择等都已经满足设计需求。
4.实用的建议和支持: 我将提供实践中的建议，比如如何利用不同的教学技术和资源，以及如何调整教学设计以更好地满足学习者的需求。
5.综合总结和理论普及: 在整个过程结束时，我还会提供一次综合性的总结，包括教学设计的关键要点和一些有用的教学理论知识，以丰富你的专业技能库。
若你准备好了，我们就可以开始这个旅程了。请告诉我你的项目或者学习内容是什么，我们将从内容分析开始。🌟
"""
        await cl.Message(
        author="教学设计开发助手（新手教师使用）",
        content=content,
        disable_feedback=True,
        ).send()
    elif chat_profile =="assistant2":
        content = """
你好！😊我是 小T，一个专为支持教学设计过程中的深入讨论和分析而生的智能工具。我的主要功能是在整个教学设计过程中，从内容分析到学习情境分析，再到教学方法的选择与应用，积极地整合用户反馈和确认。这样做的目的是确保对每一环节有详尽的理解和共识，从而创建出高效、有效且吸引人的学习体验。
我会协助你完成以下内容：
1.教学前期分析
2.教学流程设计
3.教学过程设计
我的目标是在你的教学设计旅程中提供专业的辅助和支持，确保教学目标得以实现，学习者获得高质量的学习体验。
现在，如果你已经准备好开始，就让我们一起工作来创建出色的教学设计吧！你有关于教学设计的任何问题需要我帮助解答吗？如果您有做好的教学设计，也可以直接上传，我会给您一些建议或者协助您优化。🤔
"""
        await cl.Message(
        author="教学设计开发助手（有经验教师适用）",
        content=content,
        disable_feedback=True,
        ).send()
    elif chat_profile =="assistant3":
        content = """
很高兴为您服务！🤓我是灵感助手小G，我专注于协助教师开发创新的教学活动。我的角色是作为一个虚拟助手，帮助教师在设计和实施他们的教学计划时注入新的创意和动力。
我可以为您提供的帮助包括，但不限于：
1.设计课堂互动活动，促进学生参与和合作学习。
2.开发使用新媒体和技术工具的教学策略。
3.助力于课程内容的创新呈现方法。
4.提供针对特定教学挑战的解决方案建议。
5.推荐和适配教育理念以改善学习体验。
无论您需要一些灵感、具体的策略还是教学活动的想法，我都在这里支持您，以确保您的课程既有趣又有效。😁
如果您准备好了，请对我说：“我们开始吧！”🎉
"""
        await cl.Message(
        author="教学活动灵感助手",
        content=content,
        disable_feedback=True,
        ).send()
    elif chat_profile =="assistant4":
        content = """
您好！🌈 我是 CustomEd Creator，您的个性化教学资源设计伙伴。我的使命是通过精心定制的教育内容——包括报告、剧本、测验题目、以及PPT——来支持和提升您的教学实践。无论您是在寻找具体知识点的深入测试，还是需要全面提升学生的应用技能，我都能提供精确的资源来满足您的需求。
当涉及到设计测试题目时，我将与您紧密合作，确保每一道题目都精准对接您的教学目标。我会询问所需题目的数量、题型（如选择题、填空题、测验等）、具体内容，以及测试的目的，无论是复习、评估学生理解程度，还是作为期末考试的一部分，我都将提供相应的题目及答案，确保您可以高效地用于教学或评估。
除了文本内容，我也擅长提供创意建议和设计解决方案，以生成吸引人的视觉内容，进一步关联和强化教学目标。我的终极目标是通过提升教学资源的质量，来提高您的工作效率，让您能够更专注于教学和指导学生。
如果您正在寻找定制化的教学资源，希望通过专业化的设计提升教学效果和学生的学习体验，请随时与我联系。无论您的需求是什么，我都将竭尽全力提供支持，帮助您实现教学目标。让我们携手合作，为您的教学旅程增添色彩！🎨
"""
        await cl.Message(
        author="教学资源开发助手",
        content=content,
        disable_feedback=True,
        ).send()
    elif chat_profile =="assistant5":
        content = """
老师好！🤓我是学生模拟器，一个负责模拟多种同学角色的虚拟助手。在这项任务中，我将同时模拟5个不同的学生角色，每个角色都可能有不同的特征、兴趣和知识水平。用户将扮演教师的角色，向我提供特定信息，包括学科、年级和学生的具体情况。根据这些信息，我将创建五个学生的个性和背景，并扮演他们在一个虚拟课堂情景中的表现。
作为学生，我的表现包括但不限于以下方面：
1.回答问题：我会模拟不同学生的知识水平和理解能力，给出问题的回答。
2.举手提问：如果有不清楚的概念或需要进一步的解释，我会表现出学生们的好奇心和求知欲。
3.探讨和反馈：给出简短的反馈和发起有建设性的讨论，以模拟课堂互动环境。
4.展示多样性：每个模拟学生都会有独特的个性和反应，确保课堂互动的多样性与真实感。

我需要您回答这三个问题：
1.目前我需要扮演的学生的年龄/年级
2.您打算教授的科目
3.你想象中的班级特征，比如学生们的兴趣、性格类型、以及他们对信息技术的了解程度等
回答上述的问题可以更好地定制课堂互动。当然，你也可以跟我说，现在直接开始上课！🌟
"""
        await cl.Message(
        author="学生模拟器",
        content=content,
        disable_feedback=True,
        ).send()
    elif chat_profile =="assistant6":
        content = """
您好！😊 我是 Reflective Educator，我的角色是帮助您回顾和反思已经完成的教学设计。我们将一起探讨您的设计过程，找出哪些策略或方法取得了成功，哪些可能需要改进，以及未来如何应用这些经验教训来提升您的教学实践。
具体来说，我可以帮助您：
分析教学设计的成果，辨识哪些环节对学生学习最有效。
反思实施过程中可能出现的挑战，讨论解决这些问题的策略。
思考如何更好地与学生互动，提升他们的参与度和学习兴趣。
深入讨论如何利用反馈来调整和优化您的教学设计。
鼓励您设定新的教学目标，并制定实现这些目标的具体步骤。
通过这个过程，我们将共同促进您的专业成长，并加深您对教学设计的理解。让我们一起开始吧！🌟
"""
        await cl.Message(
        author="反思助手",
        content=content,
        disable_feedback=True,
        ).send()
    


@cl.step(name="Assistant", type="run", root=True)
async def run(thread_id: str, human_query: str, file_ids: List[str] = []):
    # Add the message to the thread
    init_message = await client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=human_query, file_ids=file_ids
    )
    chat_profile = cl.user_session.get("chat_profile")
    if chat_profile =="assistant1":
        assistant_id = os.environ.get("ASSISTANT_ID_1")
    elif chat_profile =="assistant2":
        assistant_id = os.environ.get("ASSISTANT_ID_2")
    elif chat_profile =="assistant3":
        assistant_id = os.environ.get("ASSISTANT_ID_3")
    elif chat_profile =="assistant4":
        assistant_id = os.environ.get("ASSISTANT_ID_4")
    elif chat_profile =="assistant5":
        assistant_id = os.environ.get("ASSISTANT_ID_5")
    elif chat_profile =="assistant6":
        assistant_id = os.environ.get("ASSISTANT_ID_6")

    # Create the run
    run = await client.beta.threads.runs.create(
        thread_id=thread_id, assistant_id=assistant_id
    )

    message_references = {}  # type: Dict[str, cl.Message]
    step_references = {}  # type: Dict[str, cl.Step]
    tool_outputs = []
    # Periodically check for updates
    while True:
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run.id
        )

        # Fetch the run steps
        run_steps = await client.beta.threads.runs.steps.list(
            thread_id=thread_id, run_id=run.id, order="asc"
        )

        for step in run_steps.data:
            # Fetch step details
            run_step = await client.beta.threads.runs.steps.retrieve(
                thread_id=thread_id, run_id=run.id, step_id=step.id
            )
            step_details = run_step.step_details
            # Update step content in the Chainlit UI
            if step_details.type == "message_creation":
                thread_message = await client.beta.threads.messages.retrieve(
                    message_id=step_details.message_creation.message_id,
                    thread_id=thread_id,
                )
                await process_thread_message(message_references, thread_message)

            if step_details.type == "tool_calls":
                for tool_call in step_details.tool_calls:
                    if isinstance(tool_call, dict):
                        tool_call = DictToObject(tool_call)

                    if tool_call.type == "code_interpreter":
                        await process_tool_call(
                            step_references=step_references,
                            step=step,
                            tool_call=tool_call,
                            name=tool_call.type,
                            input=tool_call.code_interpreter.input
                            or "# Generating code",
                            output=tool_call.code_interpreter.outputs,
                            show_input="python",
                        )

                        tool_outputs.append(
                            {
                                "output": tool_call.code_interpreter.outputs or "",
                                "tool_call_id": tool_call.id,
                            }
                        )

                    elif tool_call.type == "retrieval":
                        await process_tool_call(
                            step_references=step_references,
                            step=step,
                            tool_call=tool_call,
                            name=tool_call.type,
                            input="Retrieving information",
                            output="Retrieved information",
                        )

                    elif tool_call.type == "function":
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        function_output = tool_map[function_name](
                            **json.loads(tool_call.function.arguments)
                        )

                        await process_tool_call(
                            step_references=step_references,
                            step=step,
                            tool_call=tool_call,
                            name=function_name,
                            input=function_args,
                            output=function_output,
                            show_input="json",
                        )

                        tool_outputs.append(
                            {"output": function_output, "tool_call_id": tool_call.id}
                        )
            if (
                run.status == "requires_action"
                and run.required_action.type == "submit_tool_outputs"
            ):
                await client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )

        await cl.sleep(2)  # Refresh every 2 seconds
        if run.status in ["cancelled", "failed", "completed", "expired"]:
            break


@cl.on_message
async def on_message(message_from_ui: cl.Message):
    thread = cl.user_session.get("thread")  # type: Thread
    files_ids = await process_files(message_from_ui.elements)
    await run(
        thread_id=thread.id, human_query=message_from_ui.content, file_ids=files_ids
    )