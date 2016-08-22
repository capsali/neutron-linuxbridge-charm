# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from test_utils import CharmTestCase
from test_utils import patch_open
from mock import patch, Mock
import neutron_ovs_context as context
import charmhelpers

TO_PATCH = [
    'config',
    'unit_get',
    'get_host_ip',
    'network_get_primary_address',
    'glob',
    'PCINetDevices',
    'relation_ids',
    'relation_get',
    'related_units',
]


def fake_context(settings):
    def outer():
        def inner():
            return settings
        return inner
    return outer


class OVSPluginContextTest(CharmTestCase):

    def setUp(self):
        super(OVSPluginContextTest, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_config.set('debug', True)
        self.test_config.set('verbose', True)
        self.test_config.set('use-syslog', True)
        self.network_get_primary_address.side_effect = NotImplementedError

    def tearDown(self):
        super(OVSPluginContextTest, self).tearDown()

    @patch('charmhelpers.contrib.openstack.context.config')
    @patch('charmhelpers.contrib.openstack.context.NeutronPortContext.'
           'resolve_ports')
    def test_data_port_name(self, mock_resolve_ports, config):
        self.test_config.set('data-port', 'br-data:em1')
        config.side_effect = self.test_config.get
        mock_resolve_ports.side_effect = lambda ports: ports
        self.assertEquals(
            charmhelpers.contrib.openstack.context.DataPortContext()(),
            {'em1': 'br-data'}
        )

    @patch('charmhelpers.contrib.openstack.context.is_phy_iface',
           lambda port: True)
    @patch('charmhelpers.contrib.openstack.context.config')
    @patch('charmhelpers.contrib.openstack.context.get_nic_hwaddr')
    @patch('charmhelpers.contrib.openstack.context.list_nics')
    def test_data_port_mac(self, list_nics, get_nic_hwaddr, config):
        machine_machs = {
            'em1': 'aa:aa:aa:aa:aa:aa',
            'eth0': 'bb:bb:bb:bb:bb:bb',
        }
        absent_mac = "cc:cc:cc:cc:cc:cc"
        config_macs = ("br-d1:%s br-d2:%s" %
                       (absent_mac, machine_machs['em1']))
        self.test_config.set('data-port', config_macs)
        config.side_effect = self.test_config.get
        list_nics.return_value = machine_machs.keys()
        get_nic_hwaddr.side_effect = lambda nic: machine_machs[nic]
        self.assertEquals(
            charmhelpers.contrib.openstack.context.DataPortContext()(),
            {'em1': 'br-d2'}
        )

    @patch.object(charmhelpers.contrib.openstack.context, 'config',
                  lambda *args: None)
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    @patch.object(charmhelpers.contrib.openstack.context, 'config')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'is_clustered')
    @patch.object(charmhelpers.contrib.openstack.context, 'https')
    @patch.object(context.OVSPluginContext, '_save_flag_file')
    @patch.object(context.OVSPluginContext, '_ensure_packages')
    @patch.object(charmhelpers.contrib.openstack.context,
                  'neutron_plugin_attribute')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_private_ip')
    def test_neutroncc_context_api_rel(self, _unit_priv_ip, _npa, _ens_pkgs,
                                       _save_ff, _https, _is_clus, _unit_get,
                                       _config, _runits, _rids, _rget):
        def mock_npa(plugin, section, manager):
            if section == "driver":
                return "neutron.randomdriver"
            if section == "config":
                return "neutron.randomconfig"

        config = {'vlan-ranges': "physnet1:1000:1500 physnet2:2000:2500",
                  'use-syslog': True,
                  'verbose': True,
                  'debug': True,
                  'bridge-mappings': "physnet1:br-data physnet2:br-data",
                  'flat-network-providers': 'physnet3 physnet4',
                  'prevent-arp-spoofing': False,
                  'enable-dpdk': False}

        def mock_config(key=None):
            if key:
                return config.get(key)

            return config

        self.maxDiff = None
        self.config.side_effect = mock_config
        _npa.side_effect = mock_npa
        _unit_get.return_value = '127.0.0.13'
        _unit_priv_ip.return_value = '127.0.0.14'
        _is_clus.return_value = False
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'l2-population': 'True',
            'network-device-mtu': 1500,
            'overlay-network-type': 'gre',
            'enable-dvr': 'True',
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.get_host_ip.return_value = '127.0.0.15'
        napi_ctxt = context.OVSPluginContext()
        expect = {
            'neutron_security_groups': True,
            'distributed_routing': True,
            'verbose': True,
            'local_ip': '127.0.0.15',
            'network_device_mtu': 1500,
            'veth_mtu': 1500,
            'config': 'neutron.randomconfig',
            'use_syslog': True,
            'enable_dpdk': False,
            'network_manager': 'neutron',
            'debug': True,
            'core_plugin': 'neutron.randomdriver',
            'neutron_plugin': 'ovs',
            'neutron_url': 'https://127.0.0.13:9696',
            'l2_population': True,
            'overlay_network_type': 'gre',
            'network_providers': 'physnet3,physnet4',
            'bridge_mappings': 'physnet1:br-data,physnet2:br-data',
            'vlan_ranges': 'physnet1:1000:1500,physnet2:2000:2500',
            'prevent_arp_spoofing': False,
        }
        self.assertEquals(expect, napi_ctxt())

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    @patch.object(charmhelpers.contrib.openstack.context, 'config')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'is_clustered')
    @patch.object(charmhelpers.contrib.openstack.context, 'https')
    @patch.object(context.OVSPluginContext, '_save_flag_file')
    @patch.object(context.OVSPluginContext, '_ensure_packages')
    @patch.object(charmhelpers.contrib.openstack.context,
                  'neutron_plugin_attribute')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_private_ip')
    def test_neutroncc_context_api_rel_disable_security(self,
                                                        _unit_priv_ip, _npa,
                                                        _ens_pkgs, _save_ff,
                                                        _https, _is_clus,
                                                        _unit_get,
                                                        _config, _runits,
                                                        _rids, _rget):
        def mock_npa(plugin, section, manager):
            if section == "driver":
                return "neutron.randomdriver"
            if section == "config":
                return "neutron.randomconfig"

        _npa.side_effect = mock_npa
        _config.return_value = 'ovs'
        _unit_get.return_value = '127.0.0.13'
        _unit_priv_ip.return_value = '127.0.0.14'
        _is_clus.return_value = False
        self.test_config.set('disable-security-groups', True)
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'l2-population': 'True',
            'network-device-mtu': 1500,
            'overlay-network-type': 'gre',
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.get_host_ip.return_value = '127.0.0.15'
        napi_ctxt = context.OVSPluginContext()
        expect = {
            'distributed_routing': False,
            'neutron_alchemy_flags': {},
            'neutron_security_groups': False,
            'verbose': True,
            'local_ip': '127.0.0.15',
            'veth_mtu': 1500,
            'network_device_mtu': 1500,
            'config': 'neutron.randomconfig',
            'use_syslog': True,
            'enable_dpdk': False,
            'network_manager': 'neutron',
            'debug': True,
            'core_plugin': 'neutron.randomdriver',
            'neutron_plugin': 'ovs',
            'neutron_url': 'https://127.0.0.13:9696',
            'l2_population': True,
            'overlay_network_type': 'gre',
            'bridge_mappings': 'physnet1:br-data',
            'vlan_ranges': 'physnet1:1000:2000',
            'prevent_arp_spoofing': True,
        }
        self.maxDiff = None
        self.assertEquals(expect, napi_ctxt())


class L3AgentContextTest(CharmTestCase):

    def setUp(self):
        super(L3AgentContextTest, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def tearDown(self):
        super(L3AgentContextTest, self).tearDown()

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_dvr_enabled(self, _runits, _rids, _rget):
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'True',
            'l2-population': 'True',
            'overlay-network-type': 'vxlan',
            'network-device-mtu': 1500,
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.assertEquals(
            context.L3AgentContext()(), {'agent_mode': 'dvr',
                                         'external_configuration_new': True}
        )

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_dvr_disabled(self, _runits, _rids, _rget):
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'False',
            'l2-population': 'True',
            'overlay-network-type': 'vxlan',
            'network-device-mtu': 1500,
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.assertEquals(context.L3AgentContext()(), {'agent_mode': 'legacy'})


class SharedSecretContext(CharmTestCase):

    def setUp(self):
        super(SharedSecretContext, self).setUp(context,
                                               TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch('os.path')
    @patch('uuid.uuid4')
    def test_secret_created_stored(self, _uuid4, _path):
        _path.exists.return_value = False
        _uuid4.return_value = 'secret_thing'
        with patch_open() as (_open, _file):
            self.assertEquals(context.get_shared_secret(),
                              'secret_thing')
            _open.assert_called_with(
                context.SHARED_SECRET.format('quantum'), 'w')
            _file.write.assert_called_with('secret_thing')

    @patch('os.path')
    def test_secret_retrieved(self, _path):
        _path.exists.return_value = True
        with patch_open() as (_open, _file):
            _file.read.return_value = 'secret_thing\n'
            self.assertEquals(context.get_shared_secret(),
                              'secret_thing')
            _open.assert_called_with(
                context.SHARED_SECRET.format('quantum'), 'r')

    @patch.object(context, 'NeutronAPIContext')
    @patch.object(context, 'get_shared_secret')
    def test_shared_secretcontext_dvr(self, _shared_secret,
                                      _NeutronAPIContext):
        _NeutronAPIContext.side_effect = fake_context({'enable_dvr': True})
        _shared_secret.return_value = 'secret_thing'
        self.assertEquals(context.SharedSecretContext()(),
                          {'shared_secret': 'secret_thing'})

    @patch.object(context, 'NeutronAPIContext')
    @patch.object(context, 'get_shared_secret')
    def test_shared_secretcontext_nodvr(self, _shared_secret,
                                        _NeutronAPIContext):
        _NeutronAPIContext.side_effect = fake_context({'enable_dvr': False})
        _shared_secret.return_value = 'secret_thing'
        self.assertEquals(context.SharedSecretContext()(), {})


class MockPCIDevice(object):
    '''Simple wrapper to mock pci.PCINetDevice class'''
    def __init__(self, address):
        self.pci_address = address


TEST_CPULIST_1 = "0-3"
TEST_CPULIST_2 = "0-7,16-23"
DPDK_DATA_PORTS = (
    "br-phynet3:fe:16:41:df:23:fe "
    "br-phynet1:fe:16:41:df:23:fd "
    "br-phynet2:fe:f2:d0:45:dc:66"
)
PCI_DEVICE_MAP = {
    'fe:16:41:df:23:fd': MockPCIDevice('0000:00:1c.0'),
    'fe:16:41:df:23:fe': MockPCIDevice('0000:00:1d.0'),
}


class TestDPDKUtils(CharmTestCase):

    def setUp(self):
        super(TestDPDKUtils, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_parse_cpu_list(self):
        self.assertEqual(context.parse_cpu_list(TEST_CPULIST_1),
                         [0, 1, 2, 3])
        self.assertEqual(context.parse_cpu_list(TEST_CPULIST_2),
                         [0, 1, 2, 3, 4, 5, 6, 7,
                          16, 17, 18, 19, 20, 21, 22, 23])

    @patch.object(context, 'parse_cpu_list', wraps=context.parse_cpu_list)
    def test_numa_node_cores(self, _parse_cpu_list):
        self.glob.glob.return_value = [
            '/sys/devices/system/node/node0'
        ]
        with patch_open() as (_, mock_file):
            mock_file.read.return_value = TEST_CPULIST_1
            self.assertEqual(context.numa_node_cores(),
                             {'0': [0, 1, 2, 3]})
        self.glob.glob.assert_called_with('/sys/devices/system/node/node*')
        _parse_cpu_list.assert_called_with(TEST_CPULIST_1)

    def test_resolve_dpdk_ports(self):
        self.test_config.set('data-port', DPDK_DATA_PORTS)
        _pci_devices = Mock()
        _pci_devices.get_device_from_mac.side_effect = PCI_DEVICE_MAP.get
        self.PCINetDevices.return_value = _pci_devices
        self.assertEqual(context.resolve_dpdk_ports(),
                         {'0000:00:1c.0': 'br-phynet1',
                          '0000:00:1d.0': 'br-phynet3'})


DPDK_PATCH = [
    'parse_cpu_list',
    'numa_node_cores',
    'resolve_dpdk_ports',
    'glob',
]

NUMA_CORES_SINGLE = {
    '0': [0, 1, 2, 3]
}

NUMA_CORES_MULTI = {
    '0': [0, 1, 2, 3],
    '1': [4, 5, 6, 7]
}


class TestOVSDPDKDeviceContext(CharmTestCase):

    def setUp(self):
        super(TestOVSDPDKDeviceContext, self).setUp(context,
                                                    TO_PATCH + DPDK_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_context = context.OVSDPDKDeviceContext()
        self.test_config.set('enable-dpdk', True)

    def test_device_whitelist(self):
        '''Test device whitelist generation'''
        self.resolve_dpdk_ports.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.assertEqual(self.test_context.device_whitelist(),
                         '-w 0000:00:1c.0 -w 0000:00:1d.0')

    def test_socket_memory(self):
        '''Test socket memory configuration'''
        self.glob.glob.return_value = ['a']
        self.assertEqual(self.test_context.socket_memory(),
                         '1024')

        self.glob.glob.return_value = ['a', 'b']
        self.assertEqual(self.test_context.socket_memory(),
                         '1024,1024')

        self.test_config.set('dpdk-socket-memory', 2048)
        self.assertEqual(self.test_context.socket_memory(),
                         '2048,2048')

    def test_cpu_mask(self):
        '''Test generation of hex CPU masks'''
        self.numa_node_cores.return_value = NUMA_CORES_SINGLE
        self.assertEqual(self.test_context.cpu_mask(), '0x01')

        self.numa_node_cores.return_value = NUMA_CORES_MULTI
        self.assertEqual(self.test_context.cpu_mask(), '0x11')

        self.test_config.set('dpdk-socket-cores', 2)
        self.assertEqual(self.test_context.cpu_mask(), '0x33')

    def test_context_no_devices(self):
        '''Ensure that DPDK is disable when no devices detected'''
        self.resolve_dpdk_ports.return_value = []
        self.assertEqual(self.test_context(), {})

    def test_context_devices(self):
        '''Ensure DPDK is enabled when devices are detected'''
        self.resolve_dpdk_ports.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.numa_node_cores.return_value = NUMA_CORES_SINGLE
        self.glob.glob.return_value = ['a']
        self.assertEqual(self.test_context(), {
            'cpu_mask': '0x01',
            'device_whitelist': '-w 0000:00:1c.0 -w 0000:00:1d.0',
            'dpdk_enabled': True,
            'socket_memory': '1024'
        })


class TestDPDKDeviceContext(CharmTestCase):

    def setUp(self):
        super(TestDPDKDeviceContext, self).setUp(context,
                                                 TO_PATCH + DPDK_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_context = context.DPDKDeviceContext()

    def test_context(self):
        self.resolve_dpdk_ports.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.assertEqual(self.test_context(), {
            'devices': ['0000:00:1c.0', '0000:00:1d.0'],
            'driver': 'uio_pci_generic'
        })
        self.config.assert_called_with('dpdk-driver')


class TestRemoteRestartContext(CharmTestCase):

    def setUp(self):
        super(TestRemoteRestartContext, self).setUp(context,
                                                    TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_restart_trigger_present(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = '8f73-f3adb96a90d8'
        self.assertEquals(
            context.RemoteRestartContext()(),
            {'restart_trigger': '8f73-f3adb96a90d8'}
        )

    def test_restart_trigger_absent(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = None
        self.assertEquals(context.RemoteRestartContext()(), {})