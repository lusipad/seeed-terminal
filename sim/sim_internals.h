// sim 内部接口:mocks.cpp 与 main_sim.cpp 之间的台词/事件通道
#pragma once
namespace sim {
const char* nextTranscript();
const char* nextReply();
bool nextSenseEvent(int& ev);  // 到时的预约事件取一次,没有则 false
}  // namespace sim
