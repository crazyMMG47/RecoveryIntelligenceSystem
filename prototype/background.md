# Background

我现在在参加一个 hackathon，信息如下：

## Hackathon overview

原始链接：
https://agents-assemble.devpost.com/?_gl=1*18ljez2*_gcl_au*MTI5MTc3MjkzOS4xNzc1MDU3NTYy*_ga*NTU3NTU0NTIzLjE3NzUwNTc1NjM.*_ga_0YHJK3Y10M*czE3NzU2MTY1MTYkbzQkZzEkdDE3NzU2MTY1NDMkajMzJGwwJGgw

举例演示视频link：
youtube.com/watch?v=Qvs_QK4meHc&time_continue=940&source_ve_path=NzY3NTg&embeds_referring_euri=https%3A%2F%2Fagents-assemble.devpost.com%2F

The Agents Assemble Hackathon is a project-based competition focused on building functional AI agents rather than standalone models.

Participants are expected to develop applications powered by large language models that can perform multi-step tasks using tools, memory, and structured workflows. The emphasis is on creating agents that go beyond simple chat interfaces and demonstrate reasoning, decision-making, and real-world utility.

Projects are typically evaluated based on:

- Agent design and capability (e.g., tool use, multi-step reasoning)
- Practical usefulness in real-world scenarios
- Technical implementation quality
- User experience and demo clarity

The hackathon encourages applications across domains such as healthcare, productivity, data analysis, and automation. Overall, it prioritizes building end-to-end, usable AI systems that showcase how agents can solve meaningful problems.

因为这是一个A2A的比赛，所以使用的LLM并不重要，我们选择gemini-3.1-flash-lite-preview, 平台是prompt opinion。prompt opinion里面我们已经输入了API Key，里面有一个内置的chat bot连着gemini。我们要做的是编写我们的agents 然后在prompt opinion里面连上我们的external agent。演示视频里面用的是ngrok。有疑问你可以访问演示视频。