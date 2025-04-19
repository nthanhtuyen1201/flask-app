import torch
from diffusers import StableDiffusionPipeline
from googletrans import Translator

# Định nghĩa tham số
rand_seed = torch.manual_seed(42)   # Đặt seed để đảm bảo tái lập kết quả
NUM_INFERENCE_STEPS = 50            # Số bước suy luận
GUIDANCE_SCALE = 0.75               # Hệ số hướng dẫn
HEIGHT = 512                        # Chiều cao ảnh đầu ra
WIDTH = 512                         # Chiều rộng ảnh đầu ra

# Danh sách model
model_list = ["nota-ai/bk-sdm-small",
              "CompVis/stable-diffusion-v1-4",
              "runwayml/stable-diffusion-v1-5",
              "prompthero/openjourney",
              "hakurei/waifu-diffusion",
              "stabilityai/stable-diffusion-2-1",
              "dreamlike-art/dreamlike-photoreal-2.0"
              ]


def create_pipeline(model_name = model_list[1]):
    # Nếu máy có GPU CUDA
    if torch.cuda.is_available():
        print("Using GPU")
        pipeline = StableDiffusionPipeline.from_pretrained(
            model_name,
            torch_dtype = torch.float16,
            use_safetensors = True
        ).to("cuda")
    elif torch.backends.mps.is_available():
        print("Using MPS")
        pipeline = StableDiffusionPipeline.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            use_safetensors=True
        ).to("mps")
    else:
        print("Using CPU")
        pipeline = StableDiffusionPipeline.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            use_safetensors=True
        )
    return pipeline

def translate_to_english(text):
    translator = Translator()
    translated_text = translator.translate(text, src="vi", dest="en").text
    return translated_text

def text2img(prompt, pipeline, height, width, style):
    # Dịch prompt sang tiếng Anh
    prompt_en = translate_to_english(prompt)

    # Thêm style vào prompt nếu cần thiết (có thể thêm các kiểu khác như 'cartoon', 'abstract')
    if style == "realistic":
        prompt_en = f"A realistic {prompt_en}"
    elif style == "cartoon":
        prompt_en = f"A cartoon style {prompt_en}"
    elif style == "abstract":
        prompt_en = f"An abstract {prompt_en}"

    # Sinh ảnh với kích thước và prompt đã thay đổi
    images = pipeline(
        prompt_en,
        guidance_scale=GUIDANCE_SCALE,
        num_inference_steps=NUM_INFERENCE_STEPS,
        generator=rand_seed,
        num_images_per_request=1,
        height=height,
        width=width
    ).images

    return images[0]

