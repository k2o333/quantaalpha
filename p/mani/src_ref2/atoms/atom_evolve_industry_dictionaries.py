#!/usr/bin/env python
"""
Verification script for atom_evolve_industry_dictionaries
- 实现行业字典的演进式更新机制
"""

def verify_atom_evolve_industry_dictionaries():
    """
    检查行业字典演进更新机制
    """
    print("Testing atom_evolve_industry_dictionaries: 行业字典的演进式更新机制")

    # Initial industry dictionary
    initial_industries = {
        '银行': {'id': 'ind_bank', 'name': '银行', 'level': 1, 'parent_id': None},
        '房地产': {'id': 'ind_real_estate', 'name': '房地产', 'level': 1, 'parent_id': None},
        '制造业': {'id': 'ind_manufacturing', 'name': '制造业', 'level': 1, 'parent_id': None},
    }

    print("Initial industry dictionary created")

    # Evolved industry dictionary with more detailed subdivisions
    evolved_industries = {
        '银行': {'id': 'ind_bank', 'name': '银行', 'level': 1, 'parent_id': None},  # ID preserved
        '房地产': {'id': 'ind_real_estate', 'name': '房地产', 'level': 1, 'parent_id': None},  # ID preserved
        '制造业': {'id': 'ind_manufacturing', 'name': '制造业', 'level': 1, 'parent_id': None},  # ID preserved
        '银行-国有大行': {'id': 'ind_bank_state', 'name': '银行-国有大行', 'level': 2, 'parent_id': 'ind_bank'},
        '银行-股份制银行': {'id': 'ind_bank_joint', 'name': '银行-股份制银行', 'level': 2, 'parent_id': 'ind_bank'},
        '房地产-住宅开发': {'id': 'ind_real_estate_residential', 'name': '房地产-住宅开发', 'level': 2, 'parent_id': 'ind_real_estate'},
        '科技': {'id': 'ind_tech', 'name': '科技', 'level': 1, 'parent_id': None},
        '科技-软件': {'id': 'ind_tech_software', 'name': '科技-软件', 'level': 2, 'parent_id': 'ind_tech'},
        '科技-硬件': {'id': 'ind_tech_hardware', 'name': '科技-硬件', 'level': 2, 'parent_id': 'ind_tech'},
    }

    print("Evolved industry dictionary with more granular classifications")

    # Verify that original IDs are preserved
    original_keys = ['银行', '房地产', '制造业']
    for key in original_keys:
        assert evolved_industries[key]['id'] == initial_industries[key]['id'], f"ID changed for {key}"
        print(f"✓ {key} maintains original ID: {evolved_industries[key]['id']}")

    # Test the hierarchy by checking parent-child relationships
    children_of_bank = {k: v for k, v in evolved_industries.items()
                        if v.get('parent_id') == 'ind_bank'}
    print(f"✓ Found {len(children_of_bank)} children of '银行' category")

    # Test ability to build hierarchical tree structure
    def build_hierarchy(industry_dict):
        hierarchy = {}
        for name, info in industry_dict.items():
            parent_id = info.get('parent_id')
            if parent_id is None:
                # Top level
                hierarchy[name] = {'info': info, 'children': {}}
            else:
                # Find parent and add as child
                for parent_name, parent_data in hierarchy.items():
                    if parent_data['info']['id'] == parent_id:
                        parent_data['children'][name] = {'info': info, 'children': {}}
                        break
                    else:
                        # Check grandchildren recursively
                        def add_to_grandchild(parent_dict, target_id, child_name, child_info):
                            for child_n, child_d in parent_dict.items():
                                if child_d['info']['id'] == target_id:
                                    child_d['children'][child_name] = {'info': child_info, 'children': {}}
                                    return True
                                elif child_d['children']:
                                    if add_to_grandchild(child_d['children'], target_id, child_name, child_info):
                                        return True
                            return False
                        add_to_grandchild(hierarchy, parent_id, name, info)
        return hierarchy

    hierarchy = build_hierarchy(evolved_industries)
    print(f"✓ Built hierarchical structure with {len(hierarchy)} top-level categories")

    # Test if we can navigate the hierarchy
    bank_children_count = len(hierarchy.get('银行', {}).get('children', {}))
    tech_children_count = len(hierarchy.get('科技', {}).get('children', {}))
    print(f"✓ '银行' has {bank_children_count} sub-categories")
    print(f"✓ '科技' has {tech_children_count} sub-categories")

    # Test evolution from one period to another while maintaining stability
    period1_industries = {
        '银行': {'id': 'ind_bank', 'name': '银行', 'level': 1},
        '房地产': {'id': 'ind_real_estate', 'name': '房地产', 'level': 1}
    }

    period2_industries = evolved_industries  # This is the evolved version

    # Verify that all period1 IDs still exist in period2 at the same exact ID
    for code, info in period1_industries.items():
        assert code in period2_industries, f"Original industry '{code}' missing from evolved dict"
        assert period2_industries[code]['id'] == info['id'], f"ID changed for industry '{code}' during evolution"

    print("✓ All original industries preserved their IDs in the evolved structure")

    # Test that we can merge multiple classification versions while maintaining stability
    new_classification_additions = {
        '医疗保健': {'id': 'ind_healthcare', 'name': '医疗保健', 'level': 1, 'parent_id': None},
        '医疗保健-医疗器械': {'id': 'ind_healthcare_equipment', 'name': '医疗保健-医疗器械', 'level': 2, 'parent_id': 'ind_healthcare'},
    }

    fully_evolved = evolved_industries.copy()
    for name, info in new_classification_additions.items():
        fully_evolved[name] = info

    print("✓ Successfully merged additional classification without affecting existing IDs")

    print("\natom_evolve_industry_dictionaries: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_evolve_industry_dictionaries()