/*
    load module to kernel:
    - sudo insmod test_mod.ko 

    remove module from kernel:
    - sudo rmmod test_mod

    Also, check:
    lsmod | grep test_mod
    modinfo test_mod

*/
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

static int test_value = 42;
static int readonly_value = 7;

/*
 * Simple integer parameter that can be modified at runtime.
 * Permissions 0644 allow root to write and everyone to read.
 */
module_param(test_value, int, 0644);
MODULE_PARM_DESC(test_value, "Simple test parameter that can be modified at runtime");

//test readonly parameter
module_param(readonly_value, int, 0444);
MODULE_PARM_DESC(readonly_value, "Read-only parameter (cannot be modified at runtime)");

static int __init test_mod_init(void)
{
    printk(KERN_INFO "Test module loaded. Current value: %d\n", test_value);
    return 0;
}

static void __exit test_mod_exit(void)
{
    printk(KERN_INFO "Test module unloaded. Final value was: %d\n", test_value);
}

module_init(test_mod_init);
module_exit(test_mod_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Nomi");
MODULE_DESCRIPTION("Small test module for developing a Python-based kernel module tool");
