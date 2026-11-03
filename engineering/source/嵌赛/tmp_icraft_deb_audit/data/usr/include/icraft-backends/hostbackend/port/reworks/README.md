Use osal for HostBackend-side operating-system adaptation.

Keep the boundary clear:
- OSAL handles OS service bindings and runtime integration differences.
- hostbackend core keeps operator behavior and backend dispatch logic.
- BSP or board initialization stays outside this layer.