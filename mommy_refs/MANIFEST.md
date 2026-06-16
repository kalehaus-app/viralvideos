# Mommy — recurring adult parent character reference set

Adult Disney/Pixar-style cartoon mom (early 30s): full adult proportions, slender adult face, warm friendly smile, soft shoulder-length brown hair, cozy sweater + jeans. Clearly an adult parent (NOT a toddler).

Model: nano_banana_pro (nano_banana_2) · 1:1 · identical description, pose varied only.

## 6 references (Higgsfield image-job IDs)
| # | Pose | Job ID | File |
|---|------|--------|------|
| 1 | standing full height | fb9d3c82-d252-4a8f-85fb-27bdd89fad97 | mom1_standing.png |
| 2 | kneeling, arms open | efb1ac4b-6556-44cd-ac6b-9cd669957961 | mom2_kneeling.png |
| 3 | front neutral | 8f6269ca-08e3-4af4-b7e9-9de35bf3be2a | mom3_front.png |
| 4 | reaching to help | 55854297-76a9-4374-aefb-38cb3416c47f | mom4_reaching.png |
| 5 | three-quarter | 55f7c3ab-66a3-427c-b0f4-4088eaf933f8 | mom5_threequarter.png |
| 6 | close-up face | 522a1957-3d42-419e-8262-9600de14c60f | mom6_closeup.png |

## To train a Mommy Soul
show_characters action=train, name="Mommy", type=soul_2, images=[the 6 job IDs above]
(~10 min). Note: training is a gated MCP action — approve it in the Higgsfield/Claude app if blocked in the web session.

## Using Pip + Mommy together in one scene
soul_2 conditions the whole image on a single soul_id, so it can't natively place two trained Souls in one shot. For Pip + Mommy scenes, use show_reference_elements (create an Element from a Mommy image) which supports multiple <<<UUID>>> placeholders alongside Pip.

## TRAINED — Mommy Soul is ready
- mommy_id: 6c889761-3c6d-45ee-8425-e6cb87dedeff
- model: soul_2 (text2image_soul_v2)
- Usage: generate_image/video with model='soul_2' + params.soul_id=6c889761-3c6d-45ee-8425-e6cb87dedeff
- Two-character tip: anchor the shot on Mommy's soul and describe Pip's signature look (curly brown hair, yellow 'Pip' romper, red-and-blue teddy) for correct adult/child scale.
