Changelog
=========

0.2.3 (2024-02-23)
------------------
ContainerManager
- reload to refresh parameters like IP adresses
- add_network() can be called with NetworkManager instance
- add change_default_route() method
NetworkManager
- reload to refresh parameters like IP adresses
- network isolation (Docker behaviour) is removed by default
ProcessManager
- switch used `iptables` binary
- `iptables` executed in complete namespace instead of network namespace only

0.2.1 (2023-11-13)
------------------
- Improve README

0.2.0 (2023-11-12)
------------------
- Release: 0.2.0 
