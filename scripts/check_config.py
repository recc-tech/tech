from config import Config

if __name__ == "__main__":
    try:
        Config()
        print("Everything looks ok!")
    except ValueError as e:
        print(f"An error occurred: {e}")
