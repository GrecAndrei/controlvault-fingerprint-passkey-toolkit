#include "../bcm_cv_host_event_shim.h"

#include <libusb.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

int
main(void)
{
  libusb_context *context = NULL;
  libusb_device_handle *device = NULL;
  int status = libusb_init(&context);
  if (status < 0) {
    fprintf(stderr, "libusb_init: %s\n", libusb_error_name(status));
    return 1;
  }

  device = libusb_open_device_with_vid_pid(context, 0x0a5c, 0x5843);
  if (device == NULL) {
    fputs("Broadcom 0a5c:5843 could not be opened\n", stderr);
    libusb_exit(context);
    return 1;
  }

  time_t now = time(NULL);
  struct tm local_time;
  if (now == (time_t) -1 || localtime_r(&now, &local_time) == NULL) {
    fputs("could not obtain local time\n", stderr);
    libusb_close(device);
    libusb_exit(context);
    return 1;
  }

  uint32_t packed = bcm_cv_pack_timestamp(&local_time);
  status = libusb_control_transfer(device, 0x40, 0x0d,
                                   (uint16_t) packed,
                                   (uint16_t) (packed >> 16),
                                   NULL, 0, 3000);
  if (status < 0) {
    fprintf(stderr, "timestamp sync: %s\n", libusb_error_name(status));
    libusb_close(device);
    libusb_exit(context);
    return 1;
  }

  printf("PASS: physical ControlVault accepted timestamp sync (packed=%08x)\n",
         packed);
  libusb_close(device);
  libusb_exit(context);
  return 0;
}
