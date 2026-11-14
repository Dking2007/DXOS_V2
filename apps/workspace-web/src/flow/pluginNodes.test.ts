// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { nodeOutputs, outputs, summary } from './nodes'
import { pluginStepConfig } from './pluginNodes'
import type { PluginStep } from './pluginNodes'
import example from '../../../../examples/plugins/tra-cuu-mst/desktiny-plugin.json'

const step: PluginStep = { plugin_id: example.id, plugin_name: example.name, ...example.nodes[0]! } as PluginStep

describe('plugin flow steps', () => {
  it('start from the plugin defaults and carry what the plugin returns', () => {
    const config = pluginStepConfig(step)
    expect(config).toEqual({
      plugin_id: 'vn.vi-du.tra-cuu-mst',
      node: 'tra_cuu_mst',
      title: 'Tra cứu mã số thuế',
      config: { ma_so: '{form.ma_so_thue}' },
      outputs: { ten_dn: 'Tên doanh nghiệp', trang_thai: 'Trạng thái hoạt động' },
    })
    expect(outputs('plugin_action', config)).toEqual(['success', 'error'])
    expect(Object.keys(nodeOutputs('tra_cuu', 'plugin_action', config, 'Tra cứu'))).toEqual([
      'tra_cuu.ok',
      'tra_cuu.ten_dn',
      'tra_cuu.trang_thai',
    ])
    expect(summary({ kind: 'plugin_action', label: '', config }, [], () => '')).toBe('Tra cứu mã số thuế')
  })
})
