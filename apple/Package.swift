// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "GongzaiCore",
    platforms: [
        .macOS(.v13),
        .iOS(.v16),
        .watchOS(.v9)
    ],
    products: [
        .library(name: "GongzaiCore", targets: ["GongzaiCore"])
    ],
    targets: [
        .target(name: "GongzaiCore"),
        .testTarget(
            name: "GongzaiCoreTests",
            dependencies: ["GongzaiCore"]
        )
    ]
)

