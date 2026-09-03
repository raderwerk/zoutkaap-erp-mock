"""Reset the ERP simulation to its deterministic initial state."""

from app.main import seed_database


def main() -> None:
    result = seed_database()
    print(f"Seed complete: {result.products} products, {result.orders} orders")


if __name__ == "__main__":
    main()
