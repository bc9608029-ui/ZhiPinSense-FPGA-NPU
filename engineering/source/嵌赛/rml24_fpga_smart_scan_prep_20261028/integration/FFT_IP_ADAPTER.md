# Procise FFT IP适配合同

不在电脑侧伪造厂商FFT。适配器必须显式记录：输入/输出顺序、缩放策略、帧指数、延迟、burst/ready语义、overflow和复位行为。

抽象边界：1024点复数s16自然时序输入；输出统一为fftshift频序、复数s26或“mantissa+逐帧exponent”。若IP原生位反转/自然序不同，由适配器重排。任何缩放必须能由Golden重建。

首轮采用独立工程/OOC综合，禁止直接覆盖当前可工作的显示/NPU位流。
