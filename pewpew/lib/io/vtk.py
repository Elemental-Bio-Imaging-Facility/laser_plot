import sys
import numpy as np

from pewpew.lib.laser import Laser


# TODO implement extent export
# TODO stretch not used for pixel extent / size


def save(path: str, laser: Laser) -> None:
    """Save data as a VTK ImageData XML."""

    # data = laser.data
    # if data.ndim < 3:
    #     data = np.reshape(data, (*data.shape, 1))
    nx, ny, nz = laser.height, laser.width, laser.depth
    print(nx, ny, nz)

    endian = "LittleEndian" if sys.byteorder == "little" else "BigEndian"

    extent = laser.extent()

    extent_str = f"0 {nx} 0 {ny} 0 {nz}"
    origin_str = f"{extent[2]} {extent[0]} 0.0"
    spacing = *laser.config.pixel_size(), laser.config.spotsize / 2.0
    spacing_str = f"{spacing[0]} {spacing[1]} {spacing[2]}"

    offset = 0
    with open(path, "wb") as fp:
        fp.write(
            (
                '<?xml version="1.0"?>\n'
                '<VTKFile type="ImageData" version="1.0" '
                f'byte_order="{endian}" header_type="UInt64">\n'
                f'<ImageData WholeExtent="{extent_str}" '
                f'Origin="{origin_str}" Spacing="{spacing_str}">\n'
                f'<Piece Extent="{extent_str}">\n'
            ).encode()
        )

        fp.write(f'<CellData Scalars="{laser.names()[0]}">\n'.encode())
        for k, v in laser.data.items():
            fp.write(
                (
                    f'<DataArray Name="{k}" type="Float64" '
                    f'format="appended" offset="{offset}"/>\n'
                ).encode()
            )
            offset += v.data.size * v.data.itemsize + 8  # blocksize
        fp.write("</CellData>\n".encode())

        fp.write(
            (
                "</Piece>\n" "</ImageData>\n" '<AppendedData encoding="raw">\n' "_"
            ).encode()
        )

        for k, v in laser.data.items():
            fp.write(np.uint64(v.data.size * v.data.itemsize))
            fp.write(v.data.ravel("F"))

        fp.write(("</AppendedData>\n" "</VTKFile>").encode())
