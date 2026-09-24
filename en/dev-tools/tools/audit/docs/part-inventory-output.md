> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/part-inventory-output.md)

# T-05 part inventory · output skeleton <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) §11.2. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T-05 Part inventory export AuditPartInventory · scope and basis](part-inventory.md) · Next page: [T-05 part inventory · same-name key follow key_follow and known limitations](part-inventory-key-follow.md) <!-- nav -->

### 11.2 Output skeleton

```json
{"tool":"part_inventory","renderer_count":170,"smr_count":112,"mr_count":58,"psr_count":21,
 "part_like_rule":"名字或任一祖先名含（大小写不敏感）：PCS Preview Icon | AreaShow | … → part_like=false",
 "avatars":[
  {"name":"…","scene_path":"…","body_path":"Body","body_sole_y":0.02,
   "body_key_count":375,"body_keys":["Breast_small_____胸_小","Foot_heel_OFF_____足_ヒールオフ","…"],
   "renderers":[
     {"path":"<outfit>/outer","type":"SkinnedMeshRenderer","part_like":true,"mesh":"…","vertex_count":1234,
      "active_self":true,"enabled":true,"material_slots":["M_outer"],
      "region_source":"bone_weights","region_weights":{"Chest":0.5,"Spine":0.3},
      "region_vertex_share":{"Chest":0.6,"Spine":0.4},"covers":["Chest","Spine"],
      "dominant_region":"Chest","boundary_edge_ratio":0.037,"closed":true,
      "sole_thickness_mm":null,"shoe_like":null,
      "switch":{"method":"m_Enabled","by_enabled":true,"by_active_self":true,
                "by_active_ancestor":true,
                "sources":[{"property":"m_Enabled","path":"<outfit>/outer",
                            "clip":"<件> ON","clip_path":"Assets/…/<件> ON.anim",
                            "controller":"<素体>_FX","controller_path":"Assets/…/<素体>_FX.controller"}]},
      "switch_method":"m_Enabled",
      "ma":{"object_toggle":false,"menu_item":false,"toggle_targets":[],"menu_item_paths":[]}},
     {"path":"…/multi-window/windowA","type":"MeshRenderer","part_like":true,"mesh":"…","vertex_count":4,
      "active_self":true,"enabled":true,"material_slots":["M_Screen"],"mesh_filter":true,
      "region_source":"nearest_bone","region_weights":{"Head":1},"region_vertex_share":{"Head":1},
      "covers":["Head"],"dominant_region":"Head","boundary_edge_ratio":null,"closed":null,
      "sole_thickness_mm":null,"shoe_like":null,
      "switch":{"method":"none","by_enabled":false,"by_active_self":false,"by_active_ancestor":false,
                "sources":[]},"switch_method":"none",
      "ma":{"object_toggle":false,"menu_item":false,"toggle_targets":[],"menu_item_paths":[]}},
     {"path":"_Plugin$功能_AvatarPoseSystem$Timer$212","type":"MeshRenderer","part_like":false,…}],
   "key_follow":{"body":"Body_b",
     "rule":"件键名 ∩ 身体被写键，且件上无写者 → candidate；只列，不判对错。",
     "body_written_keys":[{"key":"<身体胸型键>","writers":[
        {"source":"clip","path":"Body_b","key":"<身体胸型键>","clip":"<胸型档clip>",
         "clip_path":"Assets/…/<胸型档clip>.anim","controller":"<素体>_FX",
         "controller_path":"Assets/…/<素体>_FX.controller"}]}],
     "candidates":[{"renderer":"<服装>/<件B>",
        "key":"<衣服胸型键>","piece_current_weight":100.0,
        "body_writers":[{"source":"blendshape_sync","component_path":"<服装>/<件A>",
                         "reference_mesh":"Body_b","source_shape":"<衣服胸型键>",
                         "local_shape":"<衣服胸型键>"}],
        "piece_writers":[],
        "geom":{"available":true,"body_key":"…","body_delta_available":true,"body_covered_verts":812,
                "body_key_disp_mm":{"p50":3.1,"p95":9.4,"max":12.7,"count":812},
                "piece_key_disp_mm":{"p50":0.0,"p95":0.0,"max":0.0,"count":4210},
                "body_piece_dist_mm":{"at0":{"p50":5.8,"p95":11.2,"max":24.0,"count":4210},
                                      "at100":{"p50":5.9,"p95":11.3,"max":24.1,"count":4210},
                                      "p50_delta_mm":0.1}}}],
     "synced":[{"renderer":"<服装>/<件A>","key":"<身体胸型键>",
        "piece_current_weight":100.0,"body_writers":[…],
        "piece_writers":[{"source":"blendshape_sync","component_path":"<服装>/<件A>",
                          "reference_mesh":"Body_b","source_shape":"<身体胸型键>",
                          "local_shape":"<身体胸型键>"}]}],
     "candidates_by_class":{"bust":[…],"foot":[…],"other":[…]}}}]}
```

> Note (translation): `part_like_rule` reads "name or any ancestor name contains (case-insensitive): … → part_like=false"; `key_follow.rule` reads "piece key names ∩ body-written keys, and no writer on the piece → candidate; listed only, not judged right or wrong."
