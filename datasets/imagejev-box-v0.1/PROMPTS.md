# Prompts (prompt version v2)

Chat models get one user message: the image (data URL) followed by this text. Temperature 0, max 1,024 output tokens, thinking off where the model allows it. The format used per model (generic or the family's native one) was chosen on a separate 60-item dev split and frozen.

## Generic (named fractions)
```
the leftmost dog in `photo`
Find it in the image and return exactly one bounding box. Reply with JSON only, no explanation. Format: {"left": L, "top": T, "right": R, "bottom": B, "confidence": C} where L, R are fractions (0 to 1) of the image width and T, B fractions of the image height, measured from the top-left corner. C is your own probability, between 0 and 1, that your box overlaps the target with IoU of at least 0.5; always include it.
```

## Native, Qwen3 / Qwen3.5 / Qwen3.6 / Qwen3-VL (0..1000)
```
the leftmost dog in `photo`
Find it in the image and return exactly one bounding box. Reply with JSON only, no explanation. Format: {"bbox_2d": [x1, y1, x2, y2], "confidence": C} where the coordinates are integers from 0 to 1000, relative to the image width and height. C is your own probability, between 0 and 1, that your box overlaps the target with IoU of at least 0.5; always include it.
```

## Native, GLM
```
the leftmost dog in `photo`
Find it in the image and return exactly one bounding box. Reply with JSON only, no explanation. Format: {"bbox_2d": [x1, y1, x2, y2], "confidence": C} where the coordinates are integers from 0 to 1000, relative to the image width and height. You may wrap the coordinate array in <|begin_of_box|> and <|end_of_box|>. C is your own probability, between 0 and 1, that your box overlaps the target with IoU of at least 0.5; always include it.
```

## Native, Gemma ([ymin, xmin, ymax, xmax] 0..1000)
```
the leftmost dog in `photo`
Find it in the image and return exactly one bounding box. Reply with JSON only, no explanation. Format: {"bbox_2d": [ymin, xmin, ymax, xmax], "confidence": C} where the coordinates are integers from 0 to 1000, relative to the image width and height. C is your own probability, between 0 and 1, that your box overlaps the target with IoU of at least 0.5; always include it.
```

## Jev 1.14
Native TypeSafe request: `state: {"photo": "box-image"}`, the image as a base64 asset, one question `{"type": "box", "instructions": <item instructions>}`, header `TypeSafe-Danger-Zone-Images: true`, model `jev-1.14.0`.
