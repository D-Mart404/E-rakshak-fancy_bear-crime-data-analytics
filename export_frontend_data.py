import json
import os

def build_data_js():
    print("Building data.js bundle for instant frontend loading...")
    with open('entities_summary.json', 'r', encoding='utf-8') as f:
        entities_data = json.load(f)

    embedded_timelines = {}
    timeline_dir = 'entity_timelines'
    if os.path.exists(timeline_dir):
        for fname in os.listdir(timeline_dir):
            if fname.endswith('_timeline.json'):
                fpath = os.path.join(timeline_dir, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    entity_name = d['profile']['entity_name']
                    embedded_timelines[entity_name] = d['timeline']

    print(f"Loaded embedded timelines for {len(embedded_timelines)} entities.")

    master_data = {'total_events': 0, 'total_entities': 0, 'generated_at': ''}
    if os.path.exists('unified_master_timeline.json'):
        with open('unified_master_timeline.json', 'r', encoding='utf-8') as f:
            master_data = json.load(f)

    investigation_data = {}
    if os.path.exists('investigation_data.json'):
        with open('investigation_data.json', 'r', encoding='utf-8') as f:
            investigation_data = json.load(f)

    js_content = f"""// Auto-generated Frontend Data Bundle
window.ENTITIES_DATA = {json.dumps(entities_data)};
window.EMBEDDED_TIMELINES = {json.dumps(embedded_timelines)};
window.INVESTIGATION_DATA = {json.dumps(investigation_data)};
window.MASTER_STATS = {{
  total_events: {master_data.get('total_events', 0)},
  total_entities: {master_data.get('total_entities', 0)},
  generated_at: "{master_data.get('generated_at', '')}"
}};
"""

    with open('data.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    sz_mb = round(os.path.getsize('data.js') / (1024 * 1024), 2)
    print(f"Successfully generated data.js ({sz_mb} MB)")

if __name__ == '__main__':
    build_data_js()

