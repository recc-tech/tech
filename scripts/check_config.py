from config import SlidesConfig

if __name__ == "__main__":
    try:
        SlidesConfig()
        print("Everything looks ok!")
    except ValueError as e:
        print(f"An error occurred: {e}")
