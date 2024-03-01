from config import Config

if __name__ == "__main__":
    try:
        Config(strict=True)
        print("Everything looks ok!")
    except ValueError as e:
        exit(f"An error occurred: {e}")
